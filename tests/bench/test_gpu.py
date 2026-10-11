"""Tests for reading the GPU's memory without a pipe, so that a fork elsewhere cannot hold it."""

import os
import stat
import threading
import time
from pathlib import Path

import pytest

from spec_to_inspector.bench.gpu import read_gpu_memory
from spec_to_inspector.judge.timing import GpuReading


def _program(directory: Path, body: str) -> str:
    """Write an executable stand-in for `nvidia-smi`.

    Args:
        directory: Where to write it.
        body: The shell script's body.

    Returns:
        Its path.
    """
    path = directory / "fake-nvidia-smi"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


LINGER_SECONDS = 1.5
"""How long each forked child of the fork test lives on."""
FORKED_CHILDREN = 60
"""How many children the fork test forks; a count, since a fork's cost grows with the process
that runs the suite before it, and a second's worth was 41 after the console's tests."""
FORKING_SECONDS = 10.0
"""The most the fork test waits to fork them."""

SMI = """case "$1" in
  --query-gpu=memory.used) echo 10813 ;;
  --query-compute-apps=pid,used_memory) echo "4242, 8762"; echo "777, 2028" ;;
esac"""


def test_the_cards_memory_and_one_processs_are_read(tmp_path: Path) -> None:
    """Two queries, as `nvidia-smi` answers them: the card's total and the pid's own."""
    program = _program(tmp_path, SMI)
    assert read_gpu_memory(777, program=program) == GpuReading(gpu_used_mib=10813, server_mib=2028)
    assert read_gpu_memory(4242, program=program).server_mib == 8762
    assert read_gpu_memory(1, program=program) == GpuReading(gpu_used_mib=10813, server_mib=None)
    assert read_gpu_memory(None, program=program).server_mib is None


def test_a_machine_without_the_program_or_with_a_failing_one_gives_no_reading(
    tmp_path: Path,
) -> None:
    """Nothing is guessed: both figures are None."""
    assert read_gpu_memory(777, program=None) == GpuReading(None, None)
    assert read_gpu_memory(777, program=str(tmp_path / "absent")) == GpuReading(None, None)
    assert read_gpu_memory(777, program=_program(tmp_path, "exit 3")) == GpuReading(None, None)


def test_a_program_that_hangs_is_ended_at_the_timeout(tmp_path: Path) -> None:
    """A reading never takes longer than its timeout, and leaves no process behind."""
    marker = tmp_path / "pid"
    program = _program(tmp_path, f"echo $$ > {marker}\nexec sleep 30")
    started = time.perf_counter()
    reading = read_gpu_memory(777, program=program, timeout_seconds=0.3)

    assert reading == GpuReading(None, None)
    assert time.perf_counter() - started < 5
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text(encoding="utf-8")), 0)


def test_readings_do_not_wait_on_processes_forked_meanwhile(tmp_path: Path) -> None:
    """Children forked while readings are under way inherit no pipe a reading waits on.

    With a pipe, a data loader's workers forked between the pipe's making and
    the parent's closing of its write end hold that end until they exit, and
    the reading blocks for as long: the bench's first whole run got one
    reading in 17 seconds that way. Here the main thread forks children that
    linger while another thread reads; no reading may take anything like a
    child's lifetime.
    """
    program = _program(tmp_path, SMI)
    durations: list[float] = []
    readings: list[GpuReading] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            started = time.perf_counter()
            readings.append(read_gpu_memory(777, program=program))
            durations.append(time.perf_counter() - started)

    reader = threading.Thread(target=read)
    reader.start()
    children: list[int] = []
    until = time.perf_counter() + FORKING_SECONDS
    while len(children) < FORKED_CHILDREN and time.perf_counter() < until:
        child = os.fork()
        if child == 0:  # stands in for a data loader's worker: it holds what it inherited
            time.sleep(LINGER_SECONDS)
            os._exit(0)
        children.append(child)
        time.sleep(0.002)
    stop.set()
    reader.join()
    for child in children:
        os.waitpid(child, 0)

    assert len(children) == FORKED_CHILDREN
    assert set(readings) == {GpuReading(gpu_used_mib=10813, server_mib=2028)}
    assert max(durations) < LINGER_SECONDS / 2
