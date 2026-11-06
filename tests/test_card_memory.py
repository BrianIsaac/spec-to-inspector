"""Tests for reading an Intel card's memory from `xpu-smi`, against a stand-in program."""

import json
import os
import stat
import time
from pathlib import Path

import pytest
import torch

from spec_to_inspector.bench.gpu import read_gpu_memory
from spec_to_inspector.bench.run import Probes, device_probes
from spec_to_inspector.card_memory import (
    GpuReading,
    read_xpu_address,
    read_xpu_memory,
    read_xpu_name,
)
from spec_to_inspector.device import release_memory
from spec_to_inspector.judge.timing import GpuReading as TimingsReading
from spec_to_inspector.judge.timing import GpuSampler, device_sampler
from spec_to_inspector.settings import Settings


def _program(directory: Path, body: str) -> str:
    """Write an executable stand-in for `xpu-smi`.

    Args:
        directory: Where to write it.
        body: The shell script's body.

    Returns:
        Its path.
    """
    path = directory / "fake-xpu-smi"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


PROCESSES = json.dumps(
    {
        "device_util_by_proc_list": [
            {"process_id": 777, "device_id": 0, "shared_mem_size": 0, "mem_size": 1295428},
            {"process_id": 888, "device_id": 0, "shared_mem_size": 0, "mem_size": 2048},
        ]
    }
)
SMI = f"""case "$1" in
  --query-gpu=memory.used) echo 1307.2109375 ;;
  ps) echo '{PROCESSES}' ;;
esac"""


def test_the_cards_memory_and_one_processs_are_read(tmp_path: Path) -> None:
    """The card's figure is a decimal and the process's is in KiB; both arrive as whole MiB."""
    program = _program(tmp_path, SMI)
    assert read_xpu_memory(777, program=program) == GpuReading(gpu_used_mib=1307, server_mib=1265)
    assert read_xpu_memory(888, program=program).server_mib == 2


def test_a_process_not_listed_has_no_figure_but_its_card_has(tmp_path: Path) -> None:
    """A server in a container is not listed by `xpu-smi ps`: its card is still read."""
    program = _program(tmp_path, SMI)
    assert read_xpu_memory(1, program=program) == GpuReading(gpu_used_mib=1307, server_mib=None)
    assert read_xpu_memory(None, program=program) == GpuReading(gpu_used_mib=1307, server_mib=None)


def test_with_no_process_asked_about_ps_is_not_run(tmp_path: Path) -> None:
    """A reading for the card alone costs one query."""
    marker = tmp_path / "ran-ps"
    program = _program(tmp_path, f'case "$1" in ps) touch {marker} ;; *) echo 5 ;; esac')
    assert read_xpu_memory(None, program=program) == GpuReading(gpu_used_mib=5, server_mib=None)
    assert not marker.exists()


def test_the_card_is_named_to_both_queries_and_the_mask_reaches_the_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`xpu-smi` renumbers by the mask, so it must see the same mask as this process's PyTorch."""
    monkeypatch.setenv("ZE_AFFINITY_MASK", "1")
    calls = tmp_path / "calls"
    program = _program(
        tmp_path,
        f"""echo "$ZE_AFFINITY_MASK $*" >> {calls}
case "$1" in
  --query-gpu=memory.used) echo 9 ;;
  ps) echo '{{"device_util_by_proc_list": []}}' ;;
esac""",
    )
    read_xpu_memory(777, card="0000:ba:00.0", program=program)

    assert calls.read_text(encoding="utf-8").splitlines() == [
        "1 --query-gpu=memory.used --id=0000:ba:00.0 --format=csv,noheader,nounits",
        "1 ps --id 0000:ba:00.0 -j",
    ]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("exit 4", GpuReading(None, None)),
        ('case "$1" in ps) exit 4 ;; *) echo 12.5 ;; esac', GpuReading(12, None)),
        ('case "$1" in ps) echo not-json ;; *) echo 12.6 ;; esac', GpuReading(13, None)),
        ('case "$1" in ps) echo "[1]" ;; *) echo 12 ;; esac', GpuReading(12, None)),
        ("""case "$1" in ps) echo '{"other": 1}' ;; *) echo 12 ;; esac""", GpuReading(12, None)),
        (
            """case "$1" in ps) echo '{"device_util_by_proc_list": [3]}' ;; *) echo 12 ;; esac""",
            GpuReading(12, None),
        ),
        ('case "$1" in ps) echo "{}" ;; *) echo N/A ;; esac', GpuReading(None, None)),
    ],
)
def test_what_cannot_be_read_is_none_and_never_a_guess(
    tmp_path: Path, body: str, expected: GpuReading
) -> None:
    """A failure of the process's query does not cost the card's figure."""
    assert read_xpu_memory(777, program=_program(tmp_path, body)) == expected


def test_a_machine_without_the_program_gives_no_reading(tmp_path: Path) -> None:
    """On the laptop, or where the program is missing, both figures are None."""
    assert read_xpu_memory(777, program=None) == GpuReading(None, None)
    assert read_xpu_memory(777, program=str(tmp_path / "absent")) == GpuReading(None, None)


def test_a_program_that_hangs_is_ended_at_the_timeout(tmp_path: Path) -> None:
    """A reading never takes longer than its timeout, and leaves no process behind."""
    marker = tmp_path / "pid"
    program = _program(tmp_path, f"echo $$ > {marker}\nexec sleep 30")
    started = time.perf_counter()
    reading = read_xpu_memory(777, program=program, timeout_seconds=0.3)

    assert reading == GpuReading(None, None)
    assert time.perf_counter() - started < 5
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text(encoding="utf-8")), 0)


def test_the_judges_timing_and_the_bench_read_the_same_type_as_before() -> None:
    """The reading moved module; what the laptop's code imports is the same class."""
    assert TimingsReading is GpuReading


def test_the_laptops_devices_keep_the_laptops_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """On `cuda` and `cpu` the bench reads `nvidia-smi` as it did, one card for both stages."""
    monkeypatch.delenv("SPEC_TO_INSPECTOR_DEVICE", raising=False)
    for kind in ("cuda", "cpu"):
        probes = device_probes(Settings(device=kind, _env_file=None))  # pyright: ignore[reportCallIssue]
        assert probes == Probes()
        assert probes.read_gpu is read_gpu_memory
        assert probes.read_server_gpu is None


def test_the_xpu_device_reads_each_stages_own_card(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The anomaly model's stage reads this process's first card, the judge's stage the server's."""
    monkeypatch.chdir(tmp_path)
    calls = tmp_path / "calls"
    program = _program(tmp_path, f'echo "$*" >> {calls}\necho 1')
    monkeypatch.setitem(read_xpu_memory.__kwdefaults__ or {}, "program", program)

    probes = device_probes(Settings(device="xpu", vlm_card="0000:ba:00.0", _env_file=None))  # pyright: ignore[reportCallIssue]
    assert probes.read_server_gpu is not None
    probes.read_gpu(None)
    probes.read_server_gpu(None)

    lines = calls.read_text(encoding="utf-8").splitlines()
    assert lines[0].split()[1] == "--id=0"
    assert lines[1].split()[1] == "--id=0000:ba:00.0"


def test_timing_uses_measures_own_sampler_off_xpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off XPU there is no sampler to pass, so `measure` builds `nvidia-smi`'s as before."""
    monkeypatch.delenv("SPEC_TO_INSPECTOR_DEVICE", raising=False)
    assert device_sampler(Settings(_env_file=None)) is None  # pyright: ignore[reportCallIssue]
    assert device_sampler(Settings(device="cpu", _env_file=None)) is None  # pyright: ignore[reportCallIssue]


def test_timing_samples_the_servers_card_on_xpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The judge's timing reads the card the server is on, not this process's."""
    calls = tmp_path / "calls"
    program = _program(tmp_path, f'echo "$*" >> {calls}\necho 2.0')
    monkeypatch.setitem(read_xpu_memory.__kwdefaults__ or {}, "program", program)
    settings = Settings(device="xpu", vlm_card="0000:ba:00.0", _env_file=None)  # pyright: ignore[reportCallIssue]

    sampler = device_sampler(settings)

    assert isinstance(sampler, GpuSampler)
    with sampler:
        pass
    assert sampler.memory.gpu_peak_mib == 2
    assert "--id=0000:ba:00.0" in calls.read_text(encoding="utf-8").splitlines()[0]


@pytest.mark.xpu
def test_on_the_card_a_tensor_shows_on_the_card_and_on_the_process() -> None:
    """On the machine, with the real `xpu-smi`: 8 GiB moves the card and shows on the process.

    What earlier tests in this process freed can stay in the driver's pool (measured at 2.3 GiB
    after `empty_cache`) and lend the tensor memory the card already counts, so the tensor is much
    larger than that and the card is held to half of it.
    """
    release_memory(torch.device("xpu"))
    before = read_xpu_memory(os.getpid())
    tensor = torch.empty((2048, 1024, 1024), dtype=torch.float32, device="xpu:0").fill_(1.0)
    torch.xpu.synchronize()
    during = read_xpu_memory(os.getpid())
    del tensor
    release_memory(torch.device("xpu"))

    assert before.gpu_used_mib is not None
    assert during.gpu_used_mib is not None
    assert during.gpu_used_mib - before.gpu_used_mib >= 4096
    assert during.server_mib is not None
    assert during.server_mib >= 8192


def test_a_cards_name_is_read_by_its_pci_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under the mask `xpu-smi` answers N/A for a card it hides, so the name is read without it.

    The stand-in does what the real one did on 7 November 2026: `N/A` with `ZE_AFFINITY_MASK=0` set
    and the card's name with it unset, for all that the same query's memory.used is read either way.
    """
    program = _program(
        tmp_path,
        'if [ -n "$ZE_AFFINITY_MASK" ]; then echo "N/A"; '
        'elif [ "$2" = "--id=0000:ba:00.0" ]; then echo "Intel(R) Arc(TM) Pro B70 Graphics"; '
        "else exit 1; fi",
    )
    monkeypatch.setenv("ZE_AFFINITY_MASK", "0")

    assert read_xpu_name(card="0000:ba:00.0", program=program) == (
        "Intel(R) Arc(TM) Pro B70 Graphics"
    )
    assert os.environ["ZE_AFFINITY_MASK"] == "0"
    assert read_xpu_name(card="1", program=program) is None


@pytest.mark.parametrize("printed", ["N/A", "", "   "])
def test_no_name_is_read_from_what_is_not_a_name(tmp_path: Path, printed: str) -> None:
    """`N/A` is not a card's name: the record must say null, or a final run lacks nothing."""
    assert read_xpu_name(program=_program(tmp_path, f'echo "{printed}"')) is None


def test_no_name_is_read_without_the_program() -> None:
    """Null, for the record to say so."""
    assert read_xpu_name(program=None) is None


def test_the_first_visible_cards_address_is_read_under_the_mask(tmp_path: Path) -> None:
    """The mask stays, since it is what says which card is first: card 0 is `0000:17:00.0`."""
    program = _program(tmp_path, 'test "$1" = "--query-gpu=pci.bus_id" && echo "0000:17:00.0"')
    assert read_xpu_address(program=program) == "0000:17:00.0"
    assert read_xpu_address(program=None) is None
    assert read_xpu_address(program=_program(tmp_path, 'echo "N/A"')) is None
