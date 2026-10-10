"""Tests for the corrections store as the console's sink: the join to the corrections loop."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from spec_to_inspector.app.sink import (
    CorrectionSink,
    InMemorySink,
    Override,
    OverrideRefusedError,
    SinkError,
)
from spec_to_inspector.app.store_sink import StoreSink
from spec_to_inspector.corrections.override import record_override
from spec_to_inspector.corrections.recall import StoreRecall
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.spec.schema import Specification
from tests.app.console_fakes import BATCH, MODEL_SENTENCE, World, write_world
from tests.judge.run_fakes import CATEGORY

NOTE = "A pad with no part on it, not a scratch."


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The fake world, written once for the module; each test works on a copy of its run.

    Returns:
        Where its files are.
    """
    return write_world(tmp_path_factory.mktemp("store-sink"))


class Joined:
    """A store, the sink over it, and a copy of the fake run the sink writes into."""

    def __init__(self, world: World, root: Path) -> None:
        """Copy the run and bind a sink to a store that does not exist yet.

        Args:
            world: The fake world.
            root: A fresh directory.
        """
        self.runs_dir = root / "runs"
        shutil.copytree(world.run, self.runs_dir / CATEGORY / BATCH)
        self.store = CorrectionStore(root / "corrections.sqlite3")
        self.in_force: Specification | None = world.specification
        self.sink = StoreSink(
            self.store, runs_dir=self.runs_dir, specification=lambda: self.in_force
        )

    def directory(self, image_id: str) -> Path:
        """Give a board's directory in the copied run."""
        return self.runs_dir / CATEGORY / BATCH / image_id

    def override(self, **changes: object) -> Override:
        """Make the override the form would send for the board `scratch`."""
        fields: dict[str, object] = {
            "category": CATEGORY,
            "run": BATCH,
            "image_id": "scratch",
            "region_index": 1,
            "crop_path": str(self.directory("scratch") / "crops" / "region-001.png"),
            "judged_outcome": Outcome.REJECT,
            "judged_class": "scratch",
            "judged_clause": "4.1",
            "judged_reason": MODEL_SENTENCE,
            "corrected_class": "missing",
            "corrected_clause": "4.2",
            "note": NOTE,
            "created_at": "2026-10-11T02:00:00+00:00",
        }
        return Override.model_validate(fields | changes)


@pytest.fixture
def joined(world: World, tmp_path: Path) -> Joined:
    """A sink over an empty store and a fresh copy of the run.

    Returns:
        The store, the sink and the run.
    """
    return Joined(world, tmp_path)


def test_the_store_sink_is_a_correction_sink_that_reaches_the_judge(joined: Joined) -> None:
    """The store satisfies the console's protocol, and says its overrides are shown to the judge."""
    assert isinstance(joined.sink, CorrectionSink)
    assert joined.sink.reaches_judge
    assert not InMemorySink().reaches_judge


def test_an_override_goes_into_the_store_with_what_the_judge_said(joined: Joined) -> None:
    """The row is the corrections loop's own: the judged half read from the decision on disk."""
    joined.sink.record(joined.override())

    (row,) = joined.store.for_image(CATEGORY, "scratch")
    assert row.model_dump(exclude={"id", "created_at"}) == {
        "category": CATEGORY,
        "image_id": "scratch",
        "region_index": 1,
        "crop_path": str((joined.directory("scratch") / "crops" / "region-001.png").resolve()),
        "judged_class": "scratch",
        "judged_clause": "4.1",
        "judged_outcome": Outcome.REJECT,
        "judged_reason": MODEL_SENTENCE,
        "corrected_class": "missing",
        "corrected_clause": "4.2",
        "note": NOTE,
    }


def test_an_override_flags_the_decision_on_disk_and_changes_nothing_else(joined: Joined) -> None:
    """The board's `decision.json` says it was overridden; its outcome is as the judge left it."""
    before = load_decision(joined.directory("scratch"))

    joined.sink.record(joined.override())

    after = load_decision(joined.directory("scratch"))
    assert not before.corrected.overridden
    assert after.corrected.overridden
    assert after.model_dump(exclude={"corrected"}) == before.model_dump(exclude={"corrected"})


def test_the_judge_is_shown_the_override_on_the_next_board_of_the_part(joined: Joined) -> None:
    """What the form recorded is what recall puts in the next prompt: the loop is closed."""
    recall = StoreRecall(joined.store)
    assert recall.for_part(CATEGORY) == ()

    joined.sink.record(joined.override())

    (line,) = recall.for_part(CATEGORY)
    assert "the engineer corrected it to 'missing' (clause 4.2)" in line
    assert NOTE in line


def test_overrides_of_a_board_are_listed_newest_first_with_their_time(joined: Joined) -> None:
    """The card's list is the store's history of the image, in the console's own shape."""
    joined.sink.record(joined.override())
    joined.sink.record(
        joined.override(corrected_class=None, corrected_clause=None, note="On a second look.")
    )

    second, first = joined.sink.overrides_for(CATEGORY, BATCH, "scratch")

    assert (first.corrected_class, first.corrected_clause, first.note) == ("missing", "4.2", NOTE)
    assert second.says_no_defect
    assert second.note == "On a second look."
    assert (first.run, first.region_index, first.judged_class) == (BATCH, 1, "scratch")
    assert first.judged_outcome is Outcome.REJECT
    assert datetime.fromisoformat(first.created_at).tzinfo == UTC
    assert joined.sink.overrides_for(CATEGORY, BATCH, "two") == ()


def test_a_correction_made_by_the_correct_verb_shows_in_the_console(joined: Joined) -> None:
    """The verb and the form write one store; a correction without a note is still listed."""
    assert joined.in_force is not None
    record_override(
        joined.store, joined.directory("scratch"), joined.in_force, clause_id="4.2", note=""
    )

    (override,) = joined.sink.overrides_for(CATEGORY, BATCH, "scratch")

    assert (override.corrected_clause, override.note) == ("4.2", "")


def test_an_override_the_store_will_not_keep_is_refused_in_its_words(joined: Joined) -> None:
    """A correction that repeats the judge's own answer is refused, and nothing is stored."""
    with pytest.raises(OverrideRefusedError, match="repeats the judge's own answer"):
        joined.sink.record(joined.override(corrected_class="scratch", corrected_clause="4.1"))

    assert joined.store.count() == 0
    assert not load_decision(joined.directory("scratch")).corrected.overridden


def test_with_no_specification_in_force_nothing_is_recorded(joined: Joined) -> None:
    """The store checks the clause against the part's table; without a table it keeps nothing."""
    joined.in_force = None

    with pytest.raises(OverrideRefusedError, match="no specification"):
        joined.sink.record(joined.override())

    assert joined.store.count() == 0


def test_a_board_the_runs_directory_does_not_hold_is_refused(joined: Joined) -> None:
    """An override names a board by part, batch and image; one that is not there is refused."""
    with pytest.raises(OverrideRefusedError, match="holds no board"):
        joined.sink.record(joined.override(image_id="absent"))


def test_a_file_that_is_not_a_store_is_said_in_words_and_left_alone(joined: Joined) -> None:
    """A damaged corrections file stops the sink with a sentence, reading or writing."""
    joined.store.path.write_bytes(b"not a database at all, just bytes" * 40)

    with pytest.raises(SinkError, match="is not a corrections store"):
        joined.sink.overrides_for(CATEGORY, BATCH, "scratch")
    with pytest.raises(SinkError, match="is not a corrections store"):
        joined.sink.record(joined.override())

    assert joined.store.path.read_bytes().startswith(b"not a database")
