"""Tests for the written table from VisA defect type to clause."""

from pathlib import Path

import pytest

from spec_to_inspector.bench.mapping import (
    CLAUSE_MAPPING,
    PARTS,
    MappingError,
    expected_headings,
    mapping_problems,
    mapping_row,
    render_mapping_table,
)
from spec_to_inspector.datasets.visa import PUBLISHED_COUNTS
from spec_to_inspector.spec.schema import read_clause_table
from tests.spec.spec_fakes import specification

ROOT = Path(__file__).parents[2]


def test_the_table_has_one_row_for_every_defect_type_of_both_parts() -> None:
    """Four types on pcb1 and seven on pcb4, as VisA counts them."""
    for part in PARTS:
        written = {row.visa_type for row in CLAUSE_MAPPING if row.part == part}
        assert written == set(PUBLISHED_COUNTS[part].defect_types)
    assert len(CLAUSE_MAPPING) == 11


def test_the_table_is_the_tracked_clause_tables_own_mapping() -> None:
    """Every heading, row, zone and mask value agrees with the specification and with VisA."""
    tracked = read_clause_table(ROOT / "specs" / "pcb-spec.clauses.json")
    assert mapping_problems(tracked) == []


def test_a_clause_table_that_differs_is_reported_in_words() -> None:
    """Another specification has other classes, and the table says so row by row."""
    problems = mapping_problems(specification())
    assert "pcb1 melt: the specification has no clause for the class" in problems
    assert "pcb9 scratch: the table has no row for the class" in problems


def test_a_type_maps_to_its_heading_and_a_sized_type_to_its_rows() -> None:
    """The heading is zone-free; a sized type has one row per zone under it."""
    assert expected_headings("pcb4", ["burnt", "scratch", "dirt"]) == ("5.7", "5.6", "5.1")
    assert mapping_row("pcb1", "scratch").clause_ids == ("4.2.1", "4.2.2")
    assert mapping_row("pcb4", "wrong place").heading == "5.4 Misplaced component"


def test_an_unknown_type_is_an_error_not_a_guess() -> None:
    """pcb1 has no dirt clause, and nothing is mapped in its place."""
    with pytest.raises(MappingError, match="'dirt' of part pcb1"):
        expected_headings("pcb1", ["dirt"])


def test_the_table_renders_as_the_specification_units_table() -> None:
    """The rendered lines are the rows as U3 wrote them, zones in brackets."""
    lines = render_mapping_table().splitlines()
    assert lines[0] == "| Part | VisA type | Mask value | Heading | Clause ids | Rule |"
    assert (
        "| pcb1 | scratch | 3 | 4.2 Scratch | 4.2.1 (A), 4.2.2 (B) | reject over 1.0 mm, 2.0 mm |"
        in lines
    )
    assert "| pcb4 | burnt | 1 | 5.7 Burn mark | 5.7 | reject, any zone |" in lines
    assert len(lines) == 13


def test_the_tracked_mapping_file_holds_the_rendered_table() -> None:
    """`eval/clause_mapping.md` is the table, not a copy that can drift."""
    text = (ROOT / "eval" / "clause_mapping.md").read_text(encoding="utf-8")
    assert render_mapping_table() in text
