"""Training from the console: the records it shows and the one job it runs.

The Train page starts the same `spec-to-inspector train` an operator would
type, as a process of its own, and shows how long it has run and the last
line it wrote. Anomalib's fit has no progress hook of its own, so elapsed
time is shown beside how long the part's last training took, not a
percentage. The thresholds and figures on the page are read from the
`train.json` the verb leaves beside each checkpoint.
"""

import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock, Thread
from typing import Final

from spec_to_inspector.anomaly.records import TrainRecord
from spec_to_inspector.app.runs import is_name

# The layout `train` writes, <models-dir>/patchcore/<part>/train.json. Named here and not
# imported, because the module that owns it loads Anomalib, which takes ten seconds.
MODEL_FAMILY: Final = "patchcore"
RECORD_NAME: Final = "train.json"

_TAIL_BYTES: Final = 8192
_ANSI: Final = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_LINE_ENDS: Final = re.compile(r"[\r\n]+")
_STOP_SECONDS: Final = 20.0


class TrainBusyError(RuntimeError):
    """A training was asked for while another is running."""


class JobState(StrEnum):
    """Where a training job stands."""

    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


def read_train_record(models_dir: Path, category: str) -> TrainRecord | None:
    """Read a part's training record, if the part has been trained.

    Args:
        models_dir: The models directory.
        category: The part.

    Returns:
        The record, or None if there is none that can be read.
    """
    if not is_name(category):
        return None
    try:
        return TrainRecord.model_validate_json(
            (models_dir / MODEL_FAMILY / category / RECORD_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def trained_parts(models_dir: Path) -> list[str]:
    """List the parts that have a training record, by name.

    Args:
        models_dir: The models directory.

    Returns:
        The parts; empty if nothing has been trained.
    """
    family = models_dir / MODEL_FAMILY
    if not family.is_dir():
        return []
    return [
        path.name
        for path in sorted(family.iterdir())
        if path.is_dir() and read_train_record(models_dir, path.name) is not None
    ]


def train_command(category: str, *, models_dir: Path, runs_dir: Path) -> list[str]:
    """Give the command that trains a part into the console's directories.

    Args:
        category: The part.
        models_dir: The models directory.
        runs_dir: The runs directory.

    Returns:
        The `train` verb, run by this interpreter.
    """
    return [
        sys.executable,
        "-c",
        "from spec_to_inspector.cli import app; app()",
        "train",
        "--category",
        category,
        "--models-dir",
        str(models_dir),
        "--runs-dir",
        str(runs_dir),
    ]


class TrainJob:
    """One training, as a process of its own, with its log.

    Attributes:
        category: The part being trained.
        command: The command run.
        log_path: Where the command's output goes.
        started_at: When it was started, in UTC.
    """

    def __init__(self, category: str, command: Sequence[str], log_path: Path) -> None:
        """Start the command, its output going to the log.

        A command that cannot be started gives a failed job whose log says
        why, so the page has one thing to show either way.

        Args:
            category: The part being trained.
            command: The command to run.
            log_path: Where its output goes; replaced.
        """
        self.category = category
        self.command = list(command)
        self.log_path = log_path
        self.started_at = datetime.now(UTC)
        self._started = time.monotonic()
        self._ended: float | None = None
        self._returncode: int | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._waiter: Thread | None = None
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log_path.open("wb") as log:
                # Its own session, so a Ctrl-C at the console's terminal reaches the console
                # alone, which then stops the training itself and lets it clean up.
                self._process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except (OSError, ValueError) as error:
            log_path.write_text(f"the training could not be started: {error}\n", encoding="utf-8")
            self._ended = time.monotonic()
            return
        self._waiter = Thread(target=self._wait, daemon=True)
        self._waiter.start()

    def _wait(self) -> None:
        assert self._process is not None  # noqa: S101 - the waiter is started only with a process
        self._returncode = self._process.wait()
        self._ended = time.monotonic()

    @property
    def pid(self) -> int | None:
        """The process's id; None if the command could not be started."""
        return None if self._process is None else self._process.pid

    @property
    def returncode(self) -> int | None:
        """The command's exit code; None while it runs or if it never started."""
        return self._returncode

    @property
    def state(self) -> JobState:
        """Whether the training is running, finished, or failed."""
        if self._ended is None:
            return JobState.RUNNING
        return JobState.FINISHED if self._returncode == 0 else JobState.FAILED

    @property
    def elapsed_seconds(self) -> float:
        """How long the training ran, or has run so far."""
        return (self._ended if self._ended is not None else time.monotonic()) - self._started

    def tail(self, lines: int = 8) -> list[str]:
        """Read the last lines the command wrote.

        A progress bar redraws its line with carriage returns; each redraw
        counts as a line, so the last one is the bar as it stands.

        Args:
            lines: The most lines to return.

        Returns:
            The lines, oldest first, without terminal colour codes.
        """
        try:
            with self.log_path.open("rb") as log:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - _TAIL_BYTES))
                text = log.read().decode("utf-8", errors="replace")
        except OSError:
            return []
        kept = [line.strip() for line in _LINE_ENDS.split(_ANSI.sub("", text))]
        return [line for line in kept if line][-lines:]

    def last_line(self) -> str | None:
        """Read the last line the command wrote.

        Returns:
            The line, or None if it has written nothing.
        """
        tail = self.tail(1)
        return tail[0] if tail else None

    def stop(self) -> None:
        """Stop the training if it is still running, and wait for it to end."""
        if self._process is None or self._waiter is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=_STOP_SECONDS)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._waiter.join()


class TrainRunner:
    """Starts trainings, one at a time, and remembers the last."""

    def __init__(self, state_dir: Path, *, command_for: Callable[[str], Sequence[str]]) -> None:
        """Set where the logs go and how a part's command is built.

        Args:
            state_dir: The console's state directory; a job's log is
                `train-<part>.log` there.
            command_for: Gives the command that trains a part.
        """
        self._state_dir = state_dir
        self._command_for = command_for
        self._lock = Lock()
        self._latest: TrainJob | None = None

    def latest(self) -> TrainJob | None:
        """Give the last training started.

        Returns:
            The job, or None if none was started since the console came up.
        """
        with self._lock:
            return self._latest

    def start(self, category: str) -> TrainJob:
        """Start training a part.

        Args:
            category: The part.

        Returns:
            The job.

        Raises:
            TrainBusyError: If a training is still running.
        """
        with self._lock:
            running = self._latest
            if running is not None and running.state is JobState.RUNNING:
                msg = (
                    f"part {running.category} is still training; the card holds one "
                    "training at a time"
                )
                raise TrainBusyError(msg)
            self._latest = TrainJob(
                category, self._command_for(category), self._state_dir / f"train-{category}.log"
            )
            return self._latest

    def stop(self) -> None:
        """Stop the running training, if there is one; the console calls this as it shuts down."""
        with self._lock:
            job = self._latest
        if job is not None:
            job.stop()
