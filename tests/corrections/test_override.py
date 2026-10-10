"""Tests for making an override from a decision on disk, and recording it."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from spec_to_inspector.corrections.override import OverrideError, build_override, record_override
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import DECISION_NAME, judge_image, load_decision
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

SPEC = specification()
LINE = "a thin bright line scored across the board face"


def _reply(defect_class: str | None = "scratch", clause_id: str | None = "4.1") -> str:
    return json.dumps({"reason": LINE, "defect_class": defect_class, "clause_id": clause_id})


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A run of four boards, written once for the module.

    Returns:
        The run's directory.
    """
    return write_run(
        tmp_path_factory.mktemp("override"),
        {"good": "good", "scratch": "scratch", "two": "two", "speck": "speck"},
    )


@pytest.fixture(autouse=True)
def _fresh(run: Path) -> Iterator[None]:
    """Remove what a test's judging wrote."""
    yield
    for written in [*run.glob(f"*/{DECISION_NAME}"), *run.glob("*/overlays/*")]:
        written.unlink()


@pytest.fixture
def store(tmp_path: Path) -> CorrectionStore:
    """An absent store.

    Returns:
        The store.
    """
    return CorrectionStore(tmp_path / "corrections.sqlite3")


def _judged(run: Path, image_id: str, *replies: str, max_regions: int = 3) -> Decision:
    with (
        FakeVlm(list(replies) or [_reply()]) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
    ):
        return judge_image(run / image_id, SPEC, client, max_regions=max_regions)


def test_an_override_takes_the_judgement_from_the_decision(run: Path) -> None:
    """The judged half is the decision's own; the corrected half is the engineer's."""
    decision = _judged(run, "scratch")

    override = build_override(
        decision, SPEC, run / "scratch", clause_id="4.2", note="the part is gone"
    )

    assert override.category == "pcb9"
    assert override.image_id == "scratch"
    assert override.region_index == 1
    crop = (run / "scratch" / "crops" / "region-001.png").resolve()
    assert crop.is_file()
    assert override.crop_path == str(crop)
    assert (override.judged_class, override.judged_clause) == ("scratch", "4.1")
    assert override.judged_outcome is Outcome.REJECT
    assert override.judged_reason == LINE
    assert (override.corrected_class, override.corrected_clause) == ("missing", "4.2")
    assert override.note == "the part is gone"


def test_the_class_follows_from_the_clause_and_a_row_stands_for_its_heading(run: Path) -> None:
    """The engineer picks a clause; its class is the table's, and 4.1.2 is heading 4.1."""
    decision = _judged(run, "scratch", _reply("missing", "4.2"))

    override = build_override(decision, SPEC, run / "scratch", clause_id="4.1.2")

    assert (override.corrected_class, override.corrected_clause) == ("scratch", "4.1")


def test_a_class_alone_finds_its_clause(run: Path) -> None:
    """A form that posts the class without the clause is completed from the table."""
    decision = _judged(run, "scratch")

    override = build_override(decision, SPEC, run / "scratch", defect_class="missing")

    assert (override.corrected_class, override.corrected_clause) == ("missing", "4.2")


def test_neither_class_nor_clause_says_no_clause_applies(run: Path) -> None:
    """The engineer calls a false alarm."""
    decision = _judged(run, "scratch")

    override = build_override(decision, SPEC, run / "scratch", note="a reflection")

    assert override.corrected_class is None
    assert override.corrected_clause is None


def test_the_region_defaults_to_the_one_the_decision_rests_on(run: Path) -> None:
    """On a board of two regions the deciding one is overridden unless another is named."""
    decision = _judged(run, "two", _reply(), _reply())
    assert decision.deciding_region == 2

    assert build_override(decision, SPEC, run / "two", clause_id="4.2").region_index == 2
    first = build_override(decision, SPEC, run / "two", region_index=1, clause_id="4.2")
    assert first.region_index == 1
    assert first.judged_outcome is Outcome.ACCEPT


@pytest.mark.parametrize(
    ("options", "problem"),
    [
        ({"clause_id": "9.9"}, "part pcb9 has no clause 9.9; its clauses are 4.1, 4.2"),
        ({"defect_class": "burnt"}, "part pcb9 has no defect class 'burnt'"),
        ({"clause_id": "4.2", "defect_class": "scratch"}, "clause 4.2 is for 'missing'"),
        ({"clause_id": "4.1"}, "repeats the judge"),
        ({"clause_id": "4.2", "region_index": 3}, "region 3 of scratch was not judged"),
        ({"clause_id": "4.2", "note": "x" * 301}, "note"),
    ],
)
def test_an_override_the_table_or_the_decision_does_not_bear_is_refused(
    run: Path, options: dict[str, object], problem: str
) -> None:
    """A clause of another part, a class of another clause, or a region not judged."""
    decision = _judged(run, "scratch")

    with pytest.raises(OverrideError, match=problem):
        build_override(decision, SPEC, run / "scratch", **options)  # pyright: ignore[reportArgumentType]


def test_a_board_with_no_flagged_area_has_no_judgement_to_override(run: Path) -> None:
    """What the anomaly model passed, the judge never saw."""
    decision = _judged(run, "good")

    with pytest.raises(OverrideError, match="no flagged area of good was judged"):
        build_override(decision, SPEC, run / "good", clause_id="4.2")


def test_a_region_that_brought_no_answer_can_still_be_corrected(run: Path) -> None:
    """A malformed answer leaves nothing judged, and the engineer may say what it is."""
    decision = _judged(run, "scratch", "not json", "still not json")

    override = build_override(decision, SPEC, run / "scratch", clause_id="4.1")

    assert override.judged_class is None
    assert override.judged_reason is None
    assert override.judged_outcome is Outcome.NEEDS_REVIEW


def test_recording_keeps_the_row_and_marks_the_decision_overridden(
    run: Path, store: CorrectionStore
) -> None:
    """One call for the verb and for the console's form: the store, then the decision's flag."""
    decision = _judged(run, "scratch")
    assert not decision.corrected.overridden

    kept = record_override(store, run / "scratch", SPEC, clause_id="4.2", note="gone")

    assert store.for_image("pcb9", "scratch") == [kept]
    marked = load_decision(run / "scratch")
    assert marked.corrected.overridden
    assert marked.model_dump(exclude={"corrected"}) == decision.model_dump(exclude={"corrected"})


def test_nothing_is_recorded_when_the_override_is_refused(
    run: Path, store: CorrectionStore
) -> None:
    """A refused override leaves the store absent and the decision as it was."""
    decision = _judged(run, "scratch")

    with pytest.raises(OverrideError):
        record_override(store, run / "scratch", SPEC, clause_id="9.9")

    assert not store.path.exists()
    assert load_decision(run / "scratch") == decision


def test_an_image_that_was_never_judged_cannot_be_overridden(
    run: Path, store: CorrectionStore
) -> None:
    """Without a decision on disk there is no judgement; the message says what to run."""
    with pytest.raises(OverrideError, match="holds no decision; judge it first"):
        record_override(store, run / "speck", SPEC, clause_id="4.2")
    with pytest.raises(OverrideError, match="holds no decision"):
        record_override(store, run / "nowhere", SPEC, clause_id="4.2")
