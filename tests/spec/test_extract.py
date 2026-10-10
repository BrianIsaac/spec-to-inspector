"""Tests for the extraction of a specification from a document's blocks."""

import re

import pytest

from spec_to_inspector.spec.blocks import Block, Heading, Paragraph, Table
from spec_to_inspector.spec.extract import SpecificationError, extract_specification
from spec_to_inspector.spec.limits import Comparison, Unit
from spec_to_inspector.spec.schema import ANY_ZONE, Disposition

CALIBRATION_HEADER = ("Part", "Board width (mm)", "Imaged width (mm)", "Imaged height (mm)")
ZONE_HEADER = ("Part", "Zone", "Covers", "x0", "y0", "x1", "y1")
CLAUSE_HEADER = ("Clause", "Defect class", "Zone", "Limit", "Disposition")


def document() -> list[Block]:
    """Build the blocks of a small, valid, three-page specification.

    Returns:
        The blocks in reading order.
    """
    return [
        Heading(level=1, text="Workmanship specification for the fake board", page=1),
        Paragraph(text="Document X-1. Written for a test.", page=1),
        Paragraph(text="A second paragraph that is not the notice.", page=1),
        Heading(level=2, text="1 Scope", page=1),
        Paragraph(text="This covers the fake board.", page=1),
        Table(rows=(("Term", "Meaning"), ("Size", "The longest extent.")), page=1),
        Heading(level=2, text="2 Calibration and zones", page=2),
        Heading(level=3, text="2.1 Calibration", page=2),
        Table(rows=(CALIBRATION_HEADER, ("PCB9", "40.0", "50.0", "40")), page=2),
        Heading(level=3, text="2.2 Zones", page=2),
        Table(
            rows=(
                ZONE_HEADER,
                ("PCB9", "A", "The connector", "0.25", "0.25", "0.75", "0.75"),
                ("PCB9", "B", "The board face", "0", "0", "1", "1.0"),
            ),
            page=2,
        ),
        Heading(level=2, text="3 Acceptance criteria for part PCB9", page=3),
        Paragraph(text="Each clause below applies to part PCB9.", page=3),
        Heading(level=3, text="3.1 Scratch", page=3),
        Paragraph(text="A scratch is a linear mark.", page=3),
        Paragraph(text="It is rejected above the limit of its zone.", page=3),
        Table(
            rows=(
                CLAUSE_HEADER,
                ("3.1.1", "scratch", "A", "0.5 mm max", "Reject"),
                ("3.1.2", "scratch", "B", "> 1.0 mm", "Reject"),
            ),
            page=3,
        ),
        Paragraph(text="Figure 1: a scratch.", page=3),
        Heading(level=3, text="3.2 Misplaced component", page=3),
        Paragraph(text="A component off its pads is rejected.", page=3),
        Table(
            rows=(CLAUSE_HEADER, ("3.2", "Wrong  place", "Any", "Not permitted", "Reject")),
            page=3,
        ),
    ]


def replaced(index: int, block: Block) -> list[Block]:
    """Build the valid document with one block replaced.

    Args:
        index: The position of the block to replace.
        block: Its replacement.

    Returns:
        The changed blocks.
    """
    blocks = document()
    blocks[index] = block
    return blocks


def test_a_valid_document_gives_its_title_notice_calibrations_and_zones() -> None:
    """The header, the calibration table and the zone table are read as typed values."""
    spec = extract_specification(document(), pages=3)

    assert spec.title == "Workmanship specification for the fake board"
    assert spec.notice == "Document X-1. Written for a test."
    assert spec.pages == 3
    (calibration,) = spec.calibrations
    assert calibration.category == "pcb9"
    assert calibration.board_width_mm == 40.0
    assert calibration.image_width_mm == 50.0
    assert calibration.image_height_mm == 40.0
    assert calibration.page == 2
    assert [(z.category, z.name, z.title, z.rank) for z in spec.zones] == [
        ("pcb9", "A", "The connector", 1),
        ("pcb9", "B", "The board face", 2),
    ]
    assert (spec.zones[0].x0, spec.zones[0].y0, spec.zones[0].x1, spec.zones[0].y1) == (
        0.25,
        0.25,
        0.75,
        0.75,
    )
    assert spec.zones[1].page == 2


def test_a_valid_document_gives_one_clause_per_requirement_row() -> None:
    """Each row becomes a clause, with its heading, limit, page and source text."""
    spec = extract_specification(document(), pages=3)

    first, second, third = spec.clauses
    assert (first.id, first.heading_id, first.title) == ("3.1.1", "3.1", "Scratch")
    assert (first.category, first.defect_class, first.zone) == ("pcb9", "scratch", "A")
    assert (first.comparison, first.limit, first.unit) == (Comparison.GT, 0.5, Unit.MM)
    assert first.limit_text == "0.5 mm max"
    assert first.disposition is Disposition.REJECT
    assert first.page == 3
    assert first.source_text == (
        "A scratch is a linear mark. It is rejected above the limit of its zone."
    )
    assert (second.id, second.zone, second.limit, second.limit_text) == (
        "3.1.2",
        "B",
        1.0,
        "> 1.0 mm",
    )
    assert (third.id, third.heading_id, third.title) == ("3.2", "3.2", "Misplaced component")
    assert (third.defect_class, third.zone) == ("wrong place", ANY_ZONE)
    assert (third.comparison, third.limit, third.unit) == (Comparison.UNCONDITIONAL, None, None)
    assert third.source_text == "A component off its pads is rejected."


def test_a_clause_takes_the_page_of_its_heading() -> None:
    """A clause is cited by the page its number is printed on."""
    blocks = replaced(13, Heading(level=3, text="3.1 Scratch", page=2))

    spec = extract_specification(blocks, pages=3)

    assert [c.page for c in spec.clauses] == [2, 2, 3]


def test_a_review_disposition_is_read() -> None:
    """A clause may refer a defect for review instead of rejecting it."""
    blocks = replaced(
        20,
        Table(
            rows=(
                CLAUSE_HEADER,
                ("3.2", "wrong place", "Any", "Not permitted", "Refer for review"),
            ),
            page=3,
        ),
    )

    spec = extract_specification(blocks, pages=3)

    assert spec.clauses[2].disposition is Disposition.REVIEW


@pytest.mark.parametrize(
    ("index", "block", "reason"),
    [
        (0, Paragraph(text="No title here.", page=1), "title"),
        (1, Heading(level=2, text="1 Scope", page=1), "notice"),
        (3, Heading(level=3, text="1 Scope", page=1), "level 3"),
        (13, Heading(level=2, text="3.1 Scratch", page=3), "level 2"),
        (13, Heading(level=3, text="Scratch", page=3), "not numbered"),
        (13, Heading(level=3, text="4.1 Scratch", page=3), "under section 3"),
        (11, Heading(level=2, text="3 Criteria for PCB9", page=3), "acceptance criteria"),
        (14, Table(rows=(("a", "b"), ("1", "2")), page=3), "3.1"),
        (16, Paragraph(text="No table follows.", page=3), "3.1"),
        (
            16,
            Table(rows=(CLAUSE_HEADER, ("3.1.1", "scratch", "A", "0.5 mm max"), ()), page=3),
            "5 cells",
        ),
        (16, Table(rows=(CLAUSE_HEADER,), page=3), "no rows"),
        (
            16,
            Table(rows=(CLAUSE_HEADER, ("3.2.1", "scratch", "A", "0.5 mm max", "Reject")), page=3),
            "3.2.1",
        ),
        (
            16,
            Table(rows=(CLAUSE_HEADER, ("3.1.1", "scratch", "A", "0.5 mm", "Reject")), page=3),
            "no comparison",
        ),
        (
            16,
            Table(rows=(CLAUSE_HEADER, ("3.1.1", "scratch", "A", "0.5 mm max", "Scrap")), page=3),
            "disposition",
        ),
        (
            16,
            Table(rows=(CLAUSE_HEADER, ("3.1.1", "scratch", "Q", "0.5 mm max", "Reject")), page=3),
            "zone 'Q'",
        ),
        (8, Table(rows=(CALIBRATION_HEADER, ("PCB9", "wide", "50", "40")), page=2), "wide"),
        (8, Table(rows=(CALIBRATION_HEADER, ("PCB9", "4e1", "50", "40")), page=2), "4e1"),
        (
            10,
            Table(
                rows=(ZONE_HEADER, ("PCB9", "A", "The connector", "0.25", "0.25", "1.75", "0.75")),
                page=2,
            ),
            "x1",
        ),
        (8, Paragraph(text="No calibration table.", page=2), "calibration"),
    ],
)
def test_a_malformed_document_is_refused_with_its_reason(
    index: int, block: Block, reason: str
) -> None:
    """A document that does not hold together raises, naming what is wrong."""
    with pytest.raises(SpecificationError, match=re.escape(reason)):
        extract_specification(replaced(index, block), pages=3)


def test_a_clause_without_prose_is_refused() -> None:
    """A clause's requirement must be stated in words before its table."""
    blocks = document()
    del blocks[14:16]

    with pytest.raises(SpecificationError, match="states no requirement in words"):
        extract_specification(blocks, pages=3)


def test_a_clause_table_outside_a_criteria_section_is_refused() -> None:
    """Requirement rows belong to a part: a clause table elsewhere is an error."""
    blocks = replaced(
        5, Table(rows=(CLAUSE_HEADER, ("1.1", "scratch", "Any", "Not permitted", "Reject")), page=1)
    )

    with pytest.raises(SpecificationError, match="outside"):
        extract_specification(blocks, pages=3)


def test_block_text_is_held_with_single_spaces() -> None:
    """Line breaks and runs of spaces in a document's text are folded on the way in."""
    assert Paragraph(text="  two\nlines   here ", page=1).text == "two lines here"
    assert Heading(level=2, text="1  Scope\n", page=1).text == "1 Scope"
    assert Table(rows=(("a  b", " c "),), page=1).rows == (("a b", "c"),)
