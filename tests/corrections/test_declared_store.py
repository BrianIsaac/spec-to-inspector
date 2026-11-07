"""The corrections comparison's store: drawn by the seeded rule, built from the files alone."""

import hashlib
import json
from pathlib import Path

import pytest

from spec_to_inspector.bench.labels import read_labels
from spec_to_inspector.bench.record import read_record
from spec_to_inspector.corrections.declared_store import (
    NOTHING_TO_CORRECT,
    NOTHING_TO_CORRECT_TO,
    DeclaredStoreError,
    build_store,
    declared_corrections,
    draw_boards,
)
from spec_to_inspector.corrections.recall import RecallStrategy, judge_options
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.spec.schema import read_clause_table
from tests.bench.bench_fakes import label, seen

ROOT = Path(__file__).parents[2]
FINAL = ROOT / "results" / "stage2" / "final" / "bench.json"
LABELS = ROOT / "eval" / "clause_labels.csv"
CLAUSES = ROOT / "specs" / "pcb-spec.clauses.json"
TRACKED_STORE = ROOT / "results" / "stage2" / "comparison-corrections" / "store.sqlite3"

DRAWN = {
    "pcb1": (
        "bad-078",
        "bad-092",
        "bad-052",
        "bad-061",
        "bad-004",
        "bad-021",
        "bad-085",
        "bad-042",
        "bad-033",
        "bad-029",
    ),
    "pcb4": (
        "bad-077",
        "bad-096",
        "bad-059",
        "bad-065",
        "bad-011",
        "bad-026",
        "bad-051",
        "bad-044",
        "bad-038",
        "bad-015",
    ),
}
"""The twenty the addition's rule draws from the tracked labelled set, in the draw's order."""


def _built(tmp_path: Path, name: str = "store.sqlite3") -> Path:
    """Build the store from the tracked files into a scratch place.

    Args:
        tmp_path: The scratch directory.
        name: The store's file name.

    Returns:
        The store's file.
    """
    out = tmp_path / name
    build_store(FINAL, LABELS, CLAUSES, out)
    return out


def test_the_rule_draws_the_twenty_from_the_tracked_labelled_set() -> None:
    """The seed, the sort and the sample give the same twenty every time."""
    assert draw_boards(read_labels(LABELS)) == DRAWN


def test_a_part_is_drawn_with_a_generator_of_its_own() -> None:
    """One part's draw does not depend on another part being there."""
    labels = read_labels(LABELS)
    one_part = [row for row in labels if row.part == "pcb4"]
    assert draw_boards(one_part)["pcb4"] == DRAWN["pcb4"]


def test_a_multi_defect_board_is_never_drawn() -> None:
    """The draw is of single-defect boards, so the 65 stay whole."""
    labels = read_labels(LABELS)
    multi = {(row.part, row.image_id) for row in labels if not row.single}
    drawn = {(part, board) for part, boards in draw_boards(labels).items() for board in boards}
    assert not drawn & multi


def test_a_part_with_too_few_single_defect_boards_is_refused() -> None:
    """A short part stops the build, with its count."""
    with pytest.raises(DeclaredStoreError, match="pcb1 has 1 single-defect board"):
        draw_boards([label("pcb1", 0, "melt", under=("melt",))])


def test_the_store_holds_what_the_final_answered_and_what_the_label_says(tmp_path: Path) -> None:
    """The judged half is the record's, the corrected half the label's, the note the heading."""
    out = _built(tmp_path)
    store = CorrectionStore(out)

    assert store.count() == 14
    [row] = store.for_image("pcb1", "bad-092")
    assert (row.judged_class, row.judged_clause) == ("melt", "4.1")
    assert (row.corrected_class, row.corrected_clause) == ("scratch", "4.2")
    assert row.note == "Scratch"
    assert row.region_index == 1
    [row] = store.for_image("pcb4", "bad-096")
    assert (row.judged_class, row.judged_clause) == ("dirt", "5.1")
    assert (row.corrected_class, row.corrected_clause) == ("wrong place", "5.4")
    assert row.note == "Misplaced component"
    assert row.judged_reason == "A resistor is present and in place but has foreign material on it."


def test_a_board_already_right_or_with_empty_columns_holds_no_correction(tmp_path: Path) -> None:
    """The six the dated line names are drawn and hold nothing."""
    out = _built(tmp_path)
    store = CorrectionStore(out)
    for board in ("bad-021", "bad-029", "bad-078", "bad-033", "bad-061", "bad-085"):
        assert store.for_image("pcb1", board) == []


def test_the_rows_stand_in_the_draws_order_so_the_recall_takes_a_parts_last_three(
    tmp_path: Path,
) -> None:
    """The limit of three recalls the last three rows of each part, most recent first."""
    store = CorrectionStore(_built(tmp_path))

    pcb1 = store.recall_for_part("pcb1")
    pcb4 = store.recall_for_part("pcb4")

    assert [row.image_id for row in pcb1] == ["bad-042", "bad-004", "bad-052"]
    assert [row.image_id for row in pcb4] == ["bad-015", "bad-038", "bad-044"]


def test_the_product_recalls_it_as_the_settings_default_strategy_would(tmp_path: Path) -> None:
    """The product's own recall reads the store, and the note closes the line."""
    options = judge_options(CorrectionStore(_built(tmp_path)), RecallStrategy.PART)

    assert options["recall"] is not None
    lines = options["recall"]("pcb1")
    assert lines[0] == (
        "On a pcb1 board the judge called the flagged area 'melt' (clause 4.1); the engineer "
        "corrected it to 'missing' (clause 4.3). The engineer's note: Missing component."
    )
    assert options["recall_on_answer"] is None


def test_the_store_is_rebuilt_to_the_byte(tmp_path: Path) -> None:
    """The same files and the same SQLite give the same digest."""
    one = _built(tmp_path, "one.sqlite3").read_bytes()
    two = _built(tmp_path, "two.sqlite3").read_bytes()
    assert hashlib.sha256(one).hexdigest() == hashlib.sha256(two).hexdigest()


def test_building_over_an_earlier_store_replaces_it_whole(tmp_path: Path) -> None:
    """A second build does not add to the first."""
    out = _built(tmp_path)
    first = out.read_bytes()
    build_store(FINAL, LABELS, CLAUSES, out)
    assert out.read_bytes() == first


def test_every_row_is_stamped_with_the_final_runs_end_and_not_the_clock(tmp_path: Path) -> None:
    """No row carries the time of the build, which would change the digest."""
    store = CorrectionStore(_built(tmp_path))
    measured_at = read_record(FINAL).measured_at
    for part, boards in DRAWN.items():
        for board in boards:
            for row in store.for_image(part, board):
                assert row.created_at == measured_at


def test_the_manifest_says_what_each_board_became_and_what_it_was_built_from(
    tmp_path: Path,
) -> None:
    """`store.json` holds the draw, the six left out and every source by digest."""
    out = _built(tmp_path)
    manifest = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))

    assert manifest["seed"] == 20261107
    assert manifest["boards_per_part"] == 10
    assert manifest["recall"] == {"strategy": "part", "limit": 3}
    assert manifest["store"]["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert manifest["corrections"] == 14
    assert manifest["drawn"] == {part: list(boards) for part, boards in DRAWN.items()}
    assert {(board["image_id"], board["reason"]) for board in manifest["left_out"]} == {
        ("bad-021", NOTHING_TO_CORRECT),
        ("bad-029", NOTHING_TO_CORRECT),
        ("bad-078", NOTHING_TO_CORRECT),
        ("bad-033", NOTHING_TO_CORRECT_TO),
        ("bad-061", NOTHING_TO_CORRECT_TO),
        ("bad-085", NOTHING_TO_CORRECT_TO),
    }
    assert manifest["script"]["path"] == "src/spec_to_inspector/corrections/declared_store.py"
    for name, path in (("final", FINAL), ("labels", LABELS), ("clause_table", CLAUSES)):
        assert manifest[name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_tracked_store_is_what_the_script_builds_from_the_tracked_files(tmp_path: Path) -> None:
    """The comparison's file holds the rows a build gives, and its manifest names its bytes."""
    manifest = json.loads(TRACKED_STORE.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["store"]["sha256"] == hashlib.sha256(TRACKED_STORE.read_bytes()).hexdigest()
    assert manifest["store"]["path"] == "results/stage2/comparison-corrections/store.sqlite3"
    kept_script = TRACKED_STORE.with_name("declared_store.py.txt")
    assert manifest["script"]["sha256"] == hashlib.sha256(kept_script.read_bytes()).hexdigest()

    built, kept = CorrectionStore(_built(tmp_path)), CorrectionStore(TRACKED_STORE)
    assert kept.count() == built.count() == 14
    for part, boards in DRAWN.items():
        assert kept.recall_for_part(part, limit=14) == built.recall_for_part(part, limit=14)
        for board in boards:
            assert kept.for_image(part, board) == built.for_image(part, board)


def test_a_final_record_with_no_line_for_a_drawn_board_is_refused() -> None:
    """A record of other boards cannot give the judged half."""
    labels = [label("pcb1", number, "melt", under=("melt",)) for number in range(10)]
    with pytest.raises(DeclaredStoreError, match="no line for pcb1 bad-00"):
        declared_corrections(labels, [], read_clause_table(CLAUSES))


def test_a_label_whose_class_is_not_its_headings_is_refused() -> None:
    """A label and a clause table that disagree stop the build."""
    labels = [label("pcb1", number, "melt", under=("melt",)) for number in range(10)]
    # The clause table is the specification's: here it holds pcb1's 4.1 under another class.
    table = read_clause_table(CLAUSES)
    other = table.model_copy(
        update={
            "clauses": tuple(
                clause.model_copy(update={"defect_class": "bent"})
                if clause.heading_id == "4.1"
                else clause
                for clause in table.clauses
            )
        }
    )
    lines = [seen("pcb1", row.image_id, "scratch", under=("melt",)) for row in labels]
    with pytest.raises(DeclaredStoreError, match=r"clause 4\.1 is for 'bent', not 'melt'"):
        declared_corrections(labels, lines, other)
