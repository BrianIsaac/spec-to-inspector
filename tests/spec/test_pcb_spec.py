"""Tests on the demo specification itself: what it covers and what it says it is."""

from pathlib import Path

import pytest

from spec_to_inspector.datasets.visa import PUBLISHED_COUNTS
from spec_to_inspector.spec.extract import extract_specification
from spec_to_inspector.spec.limits import Comparison, Unit
from spec_to_inspector.spec.markdown import figure_sources, read_markdown
from spec_to_inspector.spec.schema import ANY_ZONE, Specification, read_clause_table

SPECS = Path(__file__).resolve().parents[2] / "specs"
MARKDOWN = SPECS / "pcb-spec.md"
CLAUSE_TABLE = SPECS / "pcb-spec.clauses.json"

# The classes of section 3.5 of the plan where a size is meaningful; every other class
# is an absence or a presence and rejects unconditionally.
SIZED = {("pcb1", "scratch"), ("pcb4", "scratch"), ("pcb4", "dirt")}


@pytest.fixture(scope="module")
def table() -> Specification:
    """Read the tracked clause table.

    Returns:
        The specification later units load.
    """
    return read_clause_table(CLAUSE_TABLE)


@pytest.mark.parametrize("category", ["pcb1", "pcb4"])
def test_the_clauses_cover_every_defect_type_visa_labels_for_the_part(
    table: Specification, category: str
) -> None:
    """Each VisA defect type of the part has clauses, spelled as VisA spells it, and no other."""
    published = PUBLISHED_COUNTS[category].defect_types

    assert set(table.defect_classes(category)) == set(published)
    for defect_type in published:
        assert table.clauses_for(category, defect_type)


def test_the_specification_covers_the_two_boards_of_the_plan_and_no_other(
    table: Specification,
) -> None:
    """PCB1 has four classes and PCB4 seven; PCB2 and PCB3 are not parts of this document."""
    assert table.categories() == ("pcb1", "pcb4")
    assert len(table.defect_classes("pcb1")) == 4
    assert len(table.defect_classes("pcb4")) == 7
    assert "wrong place" in table.defect_classes("pcb4")


def test_every_defect_type_resolves_to_one_clause_in_every_zone(table: Specification) -> None:
    """Whatever zone a region is measured in, its class leads to exactly one clause."""
    for category in table.categories():
        for defect_class in table.defect_classes(category):
            for zone in table.zones_of(category):
                clause = table.resolve(category, defect_class, zone.name)
                assert clause is not None
                assert clause.zone in (zone.name, ANY_ZONE)


def test_size_limits_only_where_a_size_is_meaningful(table: Specification) -> None:
    """Scratches and foreign material carry a limit per zone; the rest reject at any size."""
    for clause in table.clauses:
        if (clause.category, clause.defect_class) in SIZED:
            assert clause.zone != ANY_ZONE
            assert clause.comparison is Comparison.GT
            assert clause.unit is Unit.MM
            assert clause.limit is not None
            assert clause.limit > 0
        else:
            assert clause.zone == ANY_ZONE
            assert clause.comparison is Comparison.UNCONDITIONAL


def test_a_more_critical_zone_never_has_a_looser_limit(table: Specification) -> None:
    """Zone A is at least as strict as B, and B as C, for every sized class."""
    for category, defect_class in SIZED:
        limits = [
            clause.limit
            for zone in table.zones_of(category)
            if (clause := table.resolve(category, defect_class, zone.name)) is not None
        ]
        assert len(limits) == len(table.zones_of(category))
        assert limits == sorted(limits)  # pyright: ignore[reportArgumentType]


def test_each_part_has_two_or_three_zones_and_a_calibration(table: Specification) -> None:
    """The geometry the measurement needs is declared for both boards."""
    assert [len(table.zones_of(category)) for category in table.categories()] == [2, 3]
    for category in table.categories():
        calibration = table.calibration(category)
        assert calibration is not None
        assert calibration.image_width_mm > calibration.board_width_mm


def test_the_header_says_the_document_was_written_for_this_entry(table: Specification) -> None:
    """The notice under the title states what the document is and is not."""
    assert "Written for the Spec to Inspector entry" in table.notice
    assert "not a real customer's document" in table.notice
    assert "neither quotes nor paraphrases any published standard" in table.notice


def test_the_source_names_no_workmanship_standard() -> None:
    """The text is written from first principles: no standard is named, quoted or cited."""
    text = MARKDOWN.read_text(encoding="utf-8")

    for name in ("IPC", "J-STD", "A-610"):
        assert name not in text


def test_the_tracked_table_says_what_the_markdown_source_says(table: Specification) -> None:
    """Apart from page numbers, the JSON is the Markdown: neither has drifted from the other."""
    written = extract_specification(read_markdown(MARKDOWN.read_text(encoding="utf-8")), pages=1)

    assert [c.model_dump(exclude={"page"}) for c in table.clauses] == [
        c.model_dump(exclude={"page"}) for c in written.clauses
    ]
    assert [z.model_dump(exclude={"page"}) for z in table.zones] == [
        z.model_dump(exclude={"page"}) for z in written.zones
    ]


def test_every_figure_is_tracked_credited_and_built_from_visa() -> None:
    """Each picture is a file beside the source, names its VisA image and has a VisA source."""
    figures = figure_sources(MARKDOWN.read_text(encoding="utf-8"))

    assert len(figures) == 14
    for figure in figures:
        assert (SPECS / figure.path).is_file(), figure.path
        assert figure.source.startswith("visa:pcb")
        assert "(VisA pcb" in figure.caption
