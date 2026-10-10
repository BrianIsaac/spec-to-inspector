"""Tests for choosing and laying out the operator's spot-check rows."""

from pathlib import Path

import pytest

from spec_to_inspector.bench.labels import ClauseLabel, Region1, read_labels
from spec_to_inspector.bench.mapping import CLAUSE_MAPPING, expected_headings
from spec_to_inspector.bench.spot_check import (
    SPOT_CHECK_ROWS,
    allot,
    choose_rows,
    render_spot_check,
)

ROOT = Path(__file__).parents[2]


def _label(part: str, number: int, *types: str) -> ClauseLabel:
    return ClauseLabel(
        part=part,
        image_id=f"bad-{number:03d}",
        visa_image=f"{part}/Data/Images/Anomaly/{number:03d}.JPG",
        anno_line=number + 2,
        visa_types=types,
        defects="single" if len(types) == 1 else "multi",
        expected_headings=expected_headings(part, types),
        region1=Region1.NO_REGION,
        region1_types=(),
        region1_headings=(),
    )


def test_rows_are_allotted_in_proportion_with_one_for_every_stratum() -> None:
    """Largest remainders, after every stratum has its one row."""
    assert allot({"a": 54, "b": 21, "c": 8}, 10) == {"a": 6, "b": 3, "c": 1}
    assert allot({"a": 100, "b": 1, "c": 1}, 5) == {"a": 3, "b": 1, "c": 1}
    assert sum(allot({"a": 7, "b": 7, "c": 7}, 20).values()) == 20


def test_fewer_rows_than_strata_is_refused() -> None:
    """Every defect type must be seen at least once."""
    with pytest.raises(ValueError, match="3 strata"):
        allot({"a": 1, "b": 1, "c": 1}, 2)


def test_a_stratum_is_never_allotted_more_rows_than_it_has_images() -> None:
    """A rare type gives what it has and the rest goes to the others."""
    assert allot({"a": 3, "b": 1}, 4) == {"a": 3, "b": 1}
    assert allot({"a": 9, "b": 2, "c": 1}, 11) == {"a": 8, "b": 2, "c": 1}
    with pytest.raises(ValueError, match="only 4 images"):
        allot({"a": 2, "b": 2}, 5)


def test_the_choice_covers_every_type_and_repeats_exactly() -> None:
    """Twenty distinct images, every type of both parts among them, the same every time."""
    labels = read_labels(ROOT / "eval" / "clause_labels.csv")
    chosen = choose_rows(labels)

    assert len(chosen) == SPOT_CHECK_ROWS
    assert len({(row.label.part, row.label.image_id) for row in chosen}) == SPOT_CHECK_ROWS
    assert {(row.part, row.visa_type) for row in chosen} == {
        (row.part, row.visa_type) for row in CLAUSE_MAPPING
    }
    assert all(row.visa_type in row.label.visa_types for row in chosen)
    assert chosen == choose_rows(list(reversed(labels)))
    assert chosen != choose_rows(labels, seed=1)


def test_the_sheet_gives_the_path_the_types_and_the_clause_and_leaves_the_tick_blank() -> None:
    """One line per image, with nothing filled in for the operator."""
    labels = [
        _label("pcb4", 0, "burnt", "dirt"),
        _label("pcb4", 1, "dirt"),
        _label("pcb1", 3, "melt"),
    ]
    sheet = render_spot_check(choose_rows(labels, rows=3), checked_on="11 October 2026")

    assert (
        "| 1 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/003.JPG` | melt "
        "| 4.1 Stray or bridging solder |  |  |" in sheet
    )
    assert "burnt, dirt | 5.7 Burn mark; 5.1 Foreign material |  |  |" in sheet
    assert "11 October 2026" in sheet
