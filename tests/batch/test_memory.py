"""Tests for the batch's card sampler: every reading kept raw, with the stage it fell in."""

import csv
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from spec_to_inspector.batch import memory
from spec_to_inspector.batch.memory import CardSampler
from spec_to_inspector.judge.timing import GpuReading


def _steady(mib: int) -> Callable[[], GpuReading]:
    return lambda: GpuReading(gpu_used_mib=mib, server_mib=None)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sampler(path: Path, **changes: object) -> CardSampler:
    arguments: dict[str, object] = {
        "read_anomaly": _steady(100),
        "read_judge": _steady(29000),
        "interval_seconds": 0.01,
    } | changes
    return CardSampler(path, **arguments)  # pyright: ignore[reportArgumentType]


def _wait_for_a_reading(sampler: CardSampler, more_than: int) -> None:
    arrived = threading.Event()
    while not arrived.wait(0.005):
        if len(sampler.readings) > more_than:
            arrived.set()


def test_every_reading_is_kept_raw_with_both_cards_and_its_stage(tmp_path: Path) -> None:
    """The file holds one line per reading: when, which stage, and each card's memory."""
    path = tmp_path / "deep" / "cards.csv"
    with _sampler(path, stage="parse") as sampler:
        _wait_for_a_reading(sampler, 0)

    rows = _rows(path)
    assert len(rows) == len(sampler.readings) >= 2
    assert set(rows[0]) == {"utc", "seconds", "stage", "anomaly_card_mib", "judge_card_mib"}
    assert (rows[0]["stage"], rows[0]["anomaly_card_mib"], rows[0]["judge_card_mib"]) == (
        "parse",
        "100",
        "29000",
    )
    assert rows[0]["utc"].endswith("+00:00")
    assert float(rows[-1]["seconds"]) >= float(rows[0]["seconds"])


def test_the_file_is_written_as_it_goes(tmp_path: Path) -> None:
    """A run that dies keeps the readings it took: each line is flushed when it is taken."""
    path = tmp_path / "cards.csv"
    with _sampler(path) as sampler:
        _wait_for_a_reading(sampler, 1)
        assert len(_rows(path)) >= 1


def test_each_stage_has_its_peaks(tmp_path: Path) -> None:
    """A reading counts towards the stage in force when it was taken."""
    levels = iter([1860, 2594, 2000])
    last = 42

    def card_zero() -> GpuReading:
        nonlocal last
        last = next(levels, 42)
        return GpuReading(gpu_used_mib=last, server_mib=None)

    with _sampler(tmp_path / "cards.csv", read_anomaly=card_zero, stage="score") as sampler:
        _wait_for_a_reading(sampler, 3)
        sampler.enter("judge")
        seen = len(sampler.readings)
        _wait_for_a_reading(sampler, seen + 1)

    peaks = sampler.peaks()
    assert peaks["score"].anomaly_card_mib == 2594
    assert peaks["score"].judge_card_mib == 29000
    assert peaks["judge"].anomaly_card_mib == 42
    assert peaks["score"].samples + peaks["judge"].samples == len(sampler.readings)
    assert sampler.whole().anomaly_card_mib == 2594
    assert sampler.whole().samples == len(sampler.readings)


def test_a_reading_that_fails_leaves_a_blank_and_the_sampling_goes_on(tmp_path: Path) -> None:
    """`xpu-smi` can fail or hang: the reader gives None, and the raw file shows the gap."""
    path = tmp_path / "cards.csv"
    with _sampler(
        path, read_judge=lambda: GpuReading(gpu_used_mib=None, server_mib=None)
    ) as sampler:
        _wait_for_a_reading(sampler, 1)

    assert _rows(path)[0]["judge_card_mib"] == ""
    assert sampler.whole().judge_card_mib is None
    assert sampler.whole().anomaly_card_mib == 100


def test_a_reader_that_raises_does_not_end_the_run(tmp_path: Path) -> None:
    """An operating-system error in a reading is a blank, not a dead sampler."""

    def broken() -> GpuReading:
        raise OSError("no more processes")

    path = tmp_path / "cards.csv"
    with _sampler(path, read_anomaly=broken) as sampler:
        _wait_for_a_reading(sampler, 1)

    assert _rows(path)[0]["anomaly_card_mib"] == ""
    assert _rows(path)[0]["judge_card_mib"] == "29000"


def test_one_card_only_leaves_the_judges_column_blank(tmp_path: Path) -> None:
    """The laptop has one card, which holds both."""
    path = tmp_path / "cards.csv"
    with _sampler(path, read_judge=None) as sampler:
        _wait_for_a_reading(sampler, 0)

    assert _rows(path)[0]["judge_card_mib"] == ""
    assert sampler.whole().judge_card_mib is None


def test_the_interval_holds_to_a_grid_and_not_to_the_time_of_a_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reading that takes a while does not stretch the interval: `xpu-smi` takes a moment."""
    clock = [100.0]

    def slow_reading() -> GpuReading:
        clock[0] += 3.0
        return GpuReading(gpu_used_mib=1, server_mib=None)

    waits: list[float] = []

    class Stop:
        def clear(self) -> None:
            """Nothing to clear."""

        def set(self) -> None:
            """Nothing to set: this stop ends the loop on its own count."""

        def wait(self, seconds: float) -> bool:
            waits.append(seconds)
            clock[0] += seconds
            return len(waits) == 3

    monkeypatch.setattr(memory.time, "monotonic", lambda: clock[0])
    sampler = _sampler(tmp_path / "cards.csv", read_anomaly=slow_reading, interval_seconds=5.0)
    monkeypatch.setattr(sampler, "_stop", Stop())
    with sampler:
        pass

    assert waits == [2.0, 2.0, 2.0]
