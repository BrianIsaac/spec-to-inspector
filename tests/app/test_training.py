"""Tests for the console's training: the records it shows and the job it starts."""

import sys
import time
from pathlib import Path

import pytest

from spec_to_inspector.app.training import (
    JobState,
    TrainBusyError,
    TrainRunner,
    read_train_record,
    train_command,
    trained_parts,
)
from tests.anomaly.records_fakes import train_record


def _script(body: str) -> list[str]:
    return [sys.executable, "-c", body]


def _wait(runner: TrainRunner, seconds: float = 10.0) -> None:
    deadline = time.monotonic() + seconds
    job = runner.latest()
    assert job is not None
    while job.state is JobState.RUNNING:
        assert time.monotonic() < deadline, "the job did not end"
        time.sleep(0.02)


def test_a_part_with_a_record_on_disk_is_trained(tmp_path: Path) -> None:
    """The record beside a checkpoint is read; a part without one has none."""
    record = tmp_path / "patchcore" / "pcb4" / "train.json"
    record.parent.mkdir(parents=True)
    record.write_text(train_record("pcb4").model_dump_json(), encoding="utf-8")
    (tmp_path / "patchcore" / "pcb2").mkdir()
    (tmp_path / "qwen3-vl-8b-instruct-gguf").mkdir()

    assert trained_parts(tmp_path) == ["pcb4"]
    assert read_train_record(tmp_path, "pcb4") == train_record("pcb4")
    assert read_train_record(tmp_path, "pcb2") is None
    assert read_train_record(tmp_path, "../pcb4") is None
    assert trained_parts(tmp_path / "absent") == []


def test_the_command_is_the_train_verb_with_the_console_directories(tmp_path: Path) -> None:
    """The console starts the same verb an operator would type, with its own directories."""
    command = train_command("pcb4", models_dir=tmp_path / "m", runs_dir=tmp_path / "r")

    assert command[0] == sys.executable
    assert command[command.index("train") :] == [
        "train",
        "--category",
        "pcb4",
        "--models-dir",
        str(tmp_path / "m"),
        "--runs-dir",
        str(tmp_path / "r"),
    ]


def test_a_started_job_runs_and_its_last_line_is_read(tmp_path: Path) -> None:
    """While the command runs the job is running; when it ends well it is finished."""
    runner = TrainRunner(
        tmp_path,
        command_for=lambda part: _script(
            f"import sys, time; print('embedding {part}', file=sys.stderr, flush=True); "
            "time.sleep(0.3); print('coreset\\rdone 904 images', file=sys.stderr)"
        ),
    )

    job = runner.start("pcb4")

    assert runner.latest() is job
    assert job.category == "pcb4"
    assert job.state is JobState.RUNNING
    _wait(runner)
    assert job.state is JobState.FINISHED
    assert job.returncode == 0
    assert job.last_line() == "done 904 images"
    assert job.elapsed_seconds >= 0.3
    frozen = job.elapsed_seconds
    time.sleep(0.05)
    assert job.elapsed_seconds == frozen


def test_a_job_that_fails_says_so_with_its_log(tmp_path: Path) -> None:
    """A command that exits non-zero is a failed job, and its last lines are kept to show."""
    runner = TrainRunner(
        tmp_path,
        command_for=lambda _: _script(
            "import sys; print('CUDA out of memory', file=sys.stderr); sys.exit(1)"
        ),
    )

    job = runner.start("pcb4")
    _wait(runner)

    assert job.state is JobState.FAILED
    assert job.returncode == 1
    assert job.tail() == ["CUDA out of memory"]


def test_a_second_job_is_refused_while_one_runs(tmp_path: Path) -> None:
    """The card holds one training at a time."""
    runner = TrainRunner(tmp_path, command_for=lambda _: _script("import time; time.sleep(5)"))
    job = runner.start("pcb4")
    try:
        with pytest.raises(TrainBusyError, match="pcb4"):
            runner.start("pcb1")
    finally:
        job.stop()
    assert job.state is JobState.FAILED


def test_a_command_that_cannot_be_started_is_a_failed_job(tmp_path: Path) -> None:
    """A missing interpreter does not take the page down; the job says what happened."""
    runner = TrainRunner(tmp_path, command_for=lambda _: [str(tmp_path / "no-such-python")])

    job = runner.start("pcb4")

    assert job.state is JobState.FAILED
    assert "no-such-python" in job.tail()[-1]


def test_no_job_has_been_started_at_first(tmp_path: Path) -> None:
    """A new console has no training to show."""
    assert TrainRunner(tmp_path, command_for=lambda _: []).latest() is None
