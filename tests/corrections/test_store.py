"""Tests for the corrections store: what an override row holds, and what is recalled."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from spec_to_inspector.corrections.store import (
    MAX_NOTE_CHARACTERS,
    MAX_RECALL,
    CorrectionStore,
    Override,
    StoreError,
)
from spec_to_inspector.judge.disposition import Outcome


def _override(**changes: object) -> Override:
    fields: dict[str, object] = {
        "category": "pcb4",
        "image_id": "bad-016",
        "region_index": 1,
        "crop_path": "/runs/pcb4/test/bad-016/crops/region-001.png",
        "judged_class": "burnt",
        "judged_clause": "5.7",
        "judged_outcome": Outcome.REJECT,
        "judged_reason": "A blackened area on the board surface",
        "corrected_class": "damage",
        "corrected_clause": "5.5",
        "note": "the capacitor is shattered, not burnt",
    }
    return Override.model_validate(fields | changes)


@pytest.fixture
def store(tmp_path: Path) -> CorrectionStore:
    """A store whose file does not exist yet.

    Returns:
        The store.
    """
    return CorrectionStore(tmp_path / "runs" / "corrections.sqlite3")


def test_a_recorded_override_reads_back_whole_with_its_time(store: CorrectionStore) -> None:
    """Every field of the row is the override's, with an id and the time it was recorded."""
    at = datetime(2026, 10, 11, 2, 0, tzinfo=UTC)

    kept = store.record(_override(), at=at)

    assert kept.id == 1
    assert kept.created_at == "2026-10-11T02:00:00+00:00"
    assert kept.model_dump(exclude={"id", "created_at"}) == _override().model_dump()
    assert store.for_image("pcb4", "bad-016") == [kept]
    assert store.count() == 1


def test_the_time_defaults_to_now_in_utc(store: CorrectionStore) -> None:
    """An override recorded without a time is stamped when it is recorded."""
    before = datetime.now(UTC) - timedelta(seconds=1)

    kept = store.record(_override())

    stamped = datetime.fromisoformat(kept.created_at)
    assert stamped.tzinfo is not None
    assert before <= stamped <= datetime.now(UTC) + timedelta(seconds=1)


def test_a_store_that_does_not_exist_is_empty_and_stays_absent(store: CorrectionStore) -> None:
    """Reading never creates the file: an absent store is an empty one."""
    assert store.count() == 0
    assert store.recall_for_part("pcb4") == []
    assert store.recall_for_answer("pcb4", "burnt", "5.7") == []
    assert store.for_image("pcb4", "bad-016") == []
    assert not store.overridden("pcb4", "bad-016")
    assert not store.path.exists()


def test_recall_by_part_gives_the_most_recent_first(store: CorrectionStore) -> None:
    """The newest correction of the part leads; another part's is not recalled."""
    first = store.record(_override(image_id="bad-001"))
    store.record(_override(category="pcb1", image_id="bad-002", judged_class="melt"))
    last = store.record(_override(image_id="bad-003"))

    assert [c.id for c in store.recall_for_part("pcb4")] == [last.id, first.id]
    assert [c.category for c in store.recall_for_part("pcb1")] == ["pcb1"]
    assert store.recall_for_part("pcb2") == []


def test_recall_is_capped_at_three(store: CorrectionStore) -> None:
    """Five corrections of one part recall as the latest three."""
    kept = [store.record(_override(image_id=f"bad-{n:03d}")) for n in range(5)]

    assert MAX_RECALL == 3
    assert [c.id for c in store.recall_for_part("pcb4")] == [kept[4].id, kept[3].id, kept[2].id]
    assert len(store.recall_for_answer("pcb4", "burnt", "5.7")) == 3
    assert [c.id for c in store.recall_for_part("pcb4", limit=1)] == [kept[4].id]


def test_recall_by_answer_matches_what_the_judge_said_then(store: CorrectionStore) -> None:
    """Only corrections of that part, that class and that clause as judged are recalled."""
    burnt = store.record(_override(image_id="bad-001"))
    store.record(
        _override(image_id="bad-002", judged_class="dirt", judged_clause="5.1", judged_reason="x")
    )
    store.record(_override(category="pcb1", image_id="bad-003"))
    later = store.record(_override(image_id="bad-004"))

    assert [c.id for c in store.recall_for_answer("pcb4", "burnt", "5.7")] == [later.id, burnt.id]
    assert [c.image_id for c in store.recall_for_answer("pcb4", "dirt", "5.1")] == ["bad-002"]
    assert store.recall_for_answer("pcb4", "burnt", "5.1") == []
    assert store.recall_for_answer("pcb4", "scratch", "5.6") == []


def test_recall_by_answer_knows_no_clause_applies_from_no_answer(store: CorrectionStore) -> None:
    """A judge that found no clause is recalled by that; one that never answered is not."""
    nothing = store.record(_override(image_id="good-001", judged_class=None, judged_clause=None))
    store.record(
        _override(image_id="bad-009", judged_class=None, judged_clause=None, judged_reason=None)
    )

    assert [c.id for c in store.recall_for_answer("pcb4", None, None)] == [nothing.id]


def test_a_later_override_of_the_same_region_replaces_the_earlier_in_recall(
    store: CorrectionStore,
) -> None:
    """The engineer's last word on a region is the one the judge is shown; the history stays."""
    store.record(_override(corrected_class="dirt", corrected_clause="5.1"))
    other = store.record(_override(image_id="bad-020"))
    again = store.record(_override())

    assert [c.id for c in store.recall_for_part("pcb4")] == [again.id, other.id]
    assert [c.corrected_class for c in store.for_image("pcb4", "bad-016")] == ["damage", "dirt"]
    assert store.overridden("pcb4", "bad-016")
    assert not store.overridden("pcb1", "bad-016")
    assert store.count() == 3


def test_another_region_of_the_same_image_is_its_own_correction(store: CorrectionStore) -> None:
    """Two regions of one board are two corrections."""
    store.record(_override(region_index=1))
    store.record(_override(region_index=2))

    assert [c.region_index for c in store.recall_for_part("pcb4")] == [2, 1]


def test_the_engineer_may_say_no_clause_applies(store: CorrectionStore) -> None:
    """A false alarm is corrected to nothing: both the class and the clause are null."""
    kept = store.record(_override(corrected_class=None, corrected_clause=None, note="a reflection"))

    assert kept.corrected_class is None
    assert kept.corrected_clause is None


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"corrected_class": None}, "both or neither"),
        ({"corrected_clause": None}, "both or neither"),
        ({"judged_class": None}, "both or neither"),
        ({"corrected_class": "burnt", "corrected_clause": "5.7"}, "repeats the judge"),
        ({"region_index": 0}, "greater than or equal to 1"),
        ({"category": " "}, "at least 1 character"),
        ({"image_id": ""}, "at least 1 character"),
        ({"note": "x" * (MAX_NOTE_CHARACTERS + 1)}, "at most"),
        ({"corrected_clause": "five"}, "pattern"),
        ({"corrected_class": "dam4ge"}, "pattern"),
    ],
)
def test_an_override_that_is_not_one_is_refused(changes: dict[str, object], problem: str) -> None:
    """Half a correction, the judge's own answer again, or a malformed field is refused."""
    with pytest.raises(ValidationError, match=problem):
        _override(**changes)


def test_an_override_of_a_judge_that_never_answered_may_say_no_clause_applies() -> None:
    """With no valid answer on record, "no clause applies" is a correction, not a repeat."""
    kept = _override(
        judged_class=None,
        judged_clause=None,
        judged_reason=None,
        corrected_class=None,
        corrected_clause=None,
    )

    assert kept.judged_reason is None


def test_the_note_is_kept_as_one_line(store: CorrectionStore) -> None:
    """Line breaks and runs of spaces in the engineer's note are folded."""
    kept = store.record(_override(note="  shattered\n capacitor,\tnot  burnt "))

    assert kept.note == "shattered capacitor, not burnt"


def test_two_stores_on_one_file_see_each_others_rows(store: CorrectionStore) -> None:
    """The console and the command line write the same file."""
    store.record(_override())

    other = CorrectionStore(store.path)
    other.record(_override(image_id="bad-020"))

    assert store.count() == 2
    assert [c.image_id for c in store.recall_for_part("pcb4")] == ["bad-020", "bad-016"]


def test_a_file_that_is_not_a_store_is_an_error_in_words(tmp_path: Path) -> None:
    """A file of another kind, or of another layout, is refused, not overwritten."""
    path = tmp_path / "corrections.sqlite3"
    path.write_text("not a database, and long enough to be read as a header by SQLite\n" * 4)
    with pytest.raises(StoreError, match="not a corrections store"):
        CorrectionStore(path).count()
    with pytest.raises(StoreError, match="not a corrections store"):
        CorrectionStore(path).record(_override())

    newer = tmp_path / "newer.sqlite3"
    with sqlite3.connect(newer) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(StoreError, match="layout 99"):
        CorrectionStore(newer).recall_for_part("pcb4")


def test_a_limit_below_one_is_refused(store: CorrectionStore) -> None:
    """Recall is asked for at least one correction."""
    with pytest.raises(ValueError, match="at least 1"):
        store.recall_for_part("pcb4", limit=0)


def test_a_correction_copied_into_another_store_is_a_new_row_there(
    store: CorrectionStore, tmp_path: Path
) -> None:
    """A stored correction can be recorded again elsewhere; the other store numbers it itself."""
    store.record(_override(image_id="bad-001"))
    kept = store.record(_override())
    other = CorrectionStore(tmp_path / "other.sqlite3")

    copied = other.record(kept)

    assert copied.id == 1
    assert copied.model_dump(exclude={"id", "created_at"}) == _override().model_dump()


def test_a_store_whose_directory_cannot_be_made_is_an_error_in_words(tmp_path: Path) -> None:
    """A path under a file cannot hold the store; the error is the store's own."""
    (tmp_path / "runs").write_text("a file where the runs directory should be")

    with pytest.raises(StoreError, match="cannot be used"):
        CorrectionStore(tmp_path / "runs" / "corrections.sqlite3").record(_override())


def test_a_table_of_another_shape_or_a_damaged_row_is_refused(
    store: CorrectionStore, tmp_path: Path
) -> None:
    """Neither a foreign table of the same name nor a row edited by hand is read as a correction."""
    foreign = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE corrections (id INTEGER PRIMARY KEY, category TEXT)")
        connection.execute("PRAGMA user_version = 1")
    with pytest.raises(StoreError, match="cannot be used"):
        CorrectionStore(foreign).recall_for_part("pcb4")

    store.record(_override())
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE corrections SET judged_outcome = 'perhaps'")
    with pytest.raises(StoreError, match="holds a row this code cannot read"):
        store.recall_for_part("pcb4")


def test_an_empty_file_is_an_empty_store_and_takes_the_first_row(tmp_path: Path) -> None:
    """A zero-byte file reads as empty, and the first override gives it its table."""
    path = tmp_path / "corrections.sqlite3"
    path.touch()
    store = CorrectionStore(path)

    assert store.count() == 0
    assert store.recall_for_part("pcb4") == []
    assert store.record(_override()).id == 1


def test_recall_by_answer_goes_by_the_engineers_last_word_on_a_region(
    store: CorrectionStore,
) -> None:
    """An older row that matched the answer is not recalled once the region was overridden again."""
    store.record(_override())
    store.record(_override(judged_class="dirt", judged_clause="5.1", judged_reason="a dark spot"))

    assert store.recall_for_answer("pcb4", "burnt", "5.7") == []
    assert len(store.recall_for_answer("pcb4", "dirt", "5.1")) == 1


def test_the_table_is_made_once_however_many_writers_begin(store: CorrectionStore) -> None:
    """Creating the layout again in a file that has it is harmless."""
    store.record(_override())
    with sqlite3.connect(store.path) as connection:
        connection.execute("PRAGMA user_version = 0")
        tables = connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
    assert tables > 0

    with pytest.raises(StoreError, match="layout 0"):
        store.record(_override(image_id="bad-020"))
