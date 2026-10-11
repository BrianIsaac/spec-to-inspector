"""Tests for the bench's record: its file, and the comparison of a run with the one before."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from spec_to_inspector.bench.labels import read_labels
from spec_to_inspector.bench.record import (
    BenchRecord,
    compare,
    file_ref,
    read_record,
    same_making,
    write_record,
)
from spec_to_inspector.bench.run import BenchPlan
from spec_to_inspector.bench.score import score
from spec_to_inspector.judge.disposition import Outcome


def test_a_record_round_trips_through_its_file(record: BenchRecord, tmp_path: Path) -> None:
    """What is written is what is read, and no partial file is left beside it."""
    path = tmp_path / "results" / "stage1" / "bench.json"
    write_record(path, record)

    assert read_record(path) == record
    assert [entry.name for entry in path.parent.iterdir()] == ["bench.json"]
    assert "Wilson" in record.notes["proportions"]


def test_a_file_that_is_not_a_bench_record_is_refused(tmp_path: Path) -> None:
    """Another unit's figures file is not read as a run of the bench."""
    path = tmp_path / "anomaly.json"
    path.write_text('{"schema_version": 1, "unit": "U2"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        read_record(path)


def test_a_file_is_named_by_its_content(tmp_path: Path) -> None:
    """The digest is of the bytes, so an edited protocol is another protocol."""
    path = tmp_path / "PROTOCOL.md"
    path.write_text("before the run\n", encoding="utf-8")
    first = file_ref(path)
    path.write_text("after the run\n", encoding="utf-8")
    assert first.path == path.as_posix()
    assert first.sha256 != file_ref(path).sha256
    assert len(first.sha256) == 64


def test_a_run_compared_with_itself_differs_in_nothing(record: BenchRecord) -> None:
    """Seven images, four of them answered on region 1, all the same."""
    repeat = compare(record, record)

    assert (repeat.images_compared, repeat.areas_compared) == (7, 4)
    assert repeat.previous_measured_at == record.measured_at
    assert (repeat.heading_differs, repeat.class_differs, repeat.sentence_differs) == (0, 0, 0)
    assert (repeat.flag_differs, repeat.score_differs, repeat.outcome_differs) == (0, 0, 0)
    assert repeat.differing_images == []
    assert repeat.figures_equal
    assert repeat.previous_scores is None


def test_an_answer_that_changed_is_counted_and_named_and_both_figures_are_kept(
    record: BenchRecord, plan: BenchPlan
) -> None:
    """One image cites another heading the second time: the earlier figures stay on record."""
    changed = [
        observation.model_copy(
            update={
                "cited_heading": "5.5",
                "cited_class": "damage",
                "sentence": "a cracked component",
                "outcome": Outcome.NEEDS_REVIEW,
            }
        )
        if observation.key == ("pcb4", "bad-000")
        else observation
        for observation in record.observations
    ]
    later = record.model_copy(
        update={
            "observations": changed,
            "scores": score(read_labels(plan.labels), changed),
            "measured_at": "2026-10-11T09:00:00+00:00",
        }
    )
    repeat = compare(record, later)

    assert (repeat.heading_differs, repeat.class_differs, repeat.sentence_differs) == (1, 1, 1)
    assert repeat.outcome_differs == 1
    assert repeat.differing_images == ["pcb4 bad-000"]
    assert not repeat.figures_equal
    assert repeat.previous_scores == record.scores
    assert later.scores.headline.strict.all.count == 1


def test_a_score_within_the_models_own_repeatability_is_the_same_score(
    record: BenchRecord,
) -> None:
    """A difference in the fourth decimal is not a difference; one in the first is."""

    def shifted(by: float) -> BenchRecord:
        moved = [o.model_copy(update={"score": o.score + by}) for o in record.observations]
        return record.model_copy(update={"observations": moved})

    assert compare(record, shifted(2e-4)).score_differs == 0
    assert compare(record, shifted(0.5)).score_differs == 7


def test_runs_of_another_making_are_not_repeats(record: BenchRecord) -> None:
    """Another server setting or another protocol is another experiment, and is named."""
    assert same_making(record, record) == []
    judge = record.judge.model_copy(update={"image_min_tokens": "the model's own minimum"})
    other = record.model_copy(update={"judge": judge, "limit": 5})
    reasons = same_making(record, other)
    assert len(reasons) == 2
    assert reasons[0].startswith("the limit: None against 5")
    assert "the image token minimum" in reasons[1]
