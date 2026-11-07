"""Both cards' memory, read at an interval for the whole of a batch, every reading kept.

The protocol's figure 9 is peak memory by stage, read from the card's own tool. The bench reads one
card per stage at a short interval and keeps the peaks. The batch's addition asks for more: both
cards, every 5 s, for the whole run, the readings kept raw. So each reading goes to a file as it is
taken, with the stage in force, and the peaks are counted from those same readings.
"""

import contextlib
import csv
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Final, NamedTuple, Self, TextIO

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.judge.timing import GpuReading

BATCH_INTERVAL_SECONDS: Final = 5.0
"""The interval the batch's addition sets."""

COLUMNS: Final = ("utc", "seconds", "stage", "anomaly_card_mib", "judge_card_mib")
_NOT_READ: Final = GpuReading(gpu_used_mib=None, server_mib=None)


class CardPeaks(BaseModel):
    """The most memory in use on each card over some readings.

    Attributes:
        anomaly_card_mib: The anomaly model's card, or None if it was never read.
        judge_card_mib: The judge's card, or None if it was never read or there is one card.
        samples: How many readings these are over.
    """

    model_config = ConfigDict(frozen=True)

    anomaly_card_mib: int | None
    judge_card_mib: int | None
    samples: int


class CardReading(NamedTuple):
    """One reading of both cards.

    Attributes:
        utc: When it was taken, in UTC, ISO 8601.
        seconds: How long after the sampling began.
        stage: The stage in force.
        anomaly_card_mib: Memory in use on the anomaly model's card.
        judge_card_mib: Memory in use on the judge's card.
    """

    utc: str
    seconds: float
    stage: str
    anomaly_card_mib: int | None
    judge_card_mib: int | None


def _peaks(readings: list[CardReading]) -> CardPeaks:
    """Count the peaks over some readings.

    Args:
        readings: The readings.

    Returns:
        The peaks.
    """
    anomaly = [r.anomaly_card_mib for r in readings if r.anomaly_card_mib is not None]
    judge = [r.judge_card_mib for r in readings if r.judge_card_mib is not None]
    return CardPeaks(
        anomaly_card_mib=max(anomaly, default=None),
        judge_card_mib=max(judge, default=None),
        samples=len(readings),
    )


class CardSampler:
    """Reads both cards on a fixed grid for as long as it is entered, into a file as it goes."""

    def __init__(
        self,
        path: Path,
        *,
        read_anomaly: Callable[[], GpuReading],
        read_judge: Callable[[], GpuReading] | None,
        interval_seconds: float = BATCH_INTERVAL_SECONDS,
        stage: str = "start",
    ) -> None:
        """Set what is read, how often and where it goes.

        Args:
            path: The raw file; its directory is made if it is missing.
            read_anomaly: Reads the anomaly model's card.
            read_judge: Reads the judge's card; None where one card holds both.
            interval_seconds: The time between one reading's start and the next's.
            stage: The stage in force until `enter` names another.
        """
        self.path = path
        self.interval_seconds = interval_seconds
        self._read_anomaly = read_anomaly
        self._read_judge = read_judge
        self._stage = stage
        self._readings: list[CardReading] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._file: TextIO | None = None
        self._started = 0.0

    def enter(self, stage: str) -> None:
        """Name the stage the readings from now on fall in.

        Args:
            stage: The stage.
        """
        self._stage = stage

    def _take(self) -> None:
        """Take one reading, keep it, and put it in the file at once."""

        def read(reader: Callable[[], GpuReading] | None) -> GpuReading:
            if reader is None:
                return _NOT_READ
            try:
                return reader()
            except OSError:
                return _NOT_READ

        utc = datetime.now(UTC).isoformat(timespec="seconds")
        seconds = time.monotonic() - self._started
        stage = self._stage
        reading = CardReading(
            utc=utc,
            seconds=seconds,
            stage=stage,
            anomaly_card_mib=read(self._read_anomaly).gpu_used_mib,
            judge_card_mib=read(self._read_judge).gpu_used_mib,
        )
        self._readings.append(reading)
        if self._file is not None:
            line = ("" if value is None else value for value in reading)
            csv.writer(self._file, lineterminator="\n").writerow(line)
            self._file.flush()

    def _run(self) -> None:
        """Read on the grid until told to stop, then once more, so the end is read too."""
        tick = 0
        while True:
            self._take()
            tick += 1
            delay = self._started + tick * self.interval_seconds - time.monotonic()
            if self._stop.wait(max(delay, 0.0)):
                break
        self._take()

    def __enter__(self) -> Self:
        """Open the file and start reading.

        Returns:
            The sampler.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8", newline="")
        csv.writer(self._file, lineterminator="\n").writerow(COLUMNS)
        self._file.flush()
        self._started = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Stop reading and close the file, however the block ended."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        if self._file is not None:
            with contextlib.suppress(OSError):
                self._file.close()

    @property
    def readings(self) -> list[CardReading]:
        """The readings taken so far, in order."""
        return list(self._readings)

    def peaks(self) -> dict[str, CardPeaks]:
        """Count each stage's peaks from the readings.

        Returns:
            The peaks by stage, in the order the stages came.
        """
        stages: dict[str, list[CardReading]] = {}
        for reading in self.readings:
            stages.setdefault(reading.stage, []).append(reading)
        return {stage: _peaks(readings) for stage, readings in stages.items()}

    def whole(self) -> CardPeaks:
        """Count the peaks over every reading.

        Returns:
            The peaks.
        """
        return _peaks(self.readings)
