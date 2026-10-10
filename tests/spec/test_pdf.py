"""The round trip: the specification's PDF parses back to exactly what its Markdown says.

These tests run docling on the tracked PDF, on the CPU. docling's layout and
table models (530 MB) are fetched into the Hugging Face cache on first use.
"""

from pathlib import Path

import pypdfium2
import pytest

from spec_to_inspector.spec.blocks import Heading
from spec_to_inspector.spec.extract import extract_specification
from spec_to_inspector.spec.limits import Comparison, Unit
from spec_to_inspector.spec.markdown import read_markdown
from spec_to_inspector.spec.pdf import ParsedPdf, PdfError, read_pdf
from spec_to_inspector.spec.schema import ANY_ZONE, Specification, read_clause_table

SPECS = Path(__file__).resolve().parents[2] / "specs"
PDF = SPECS / "pcb-spec.pdf"
MARKDOWN = SPECS / "pcb-spec.md"
CLAUSE_TABLE = SPECS / "pcb-spec.clauses.json"

GT, NONE = Comparison.GT, Comparison.UNCONDITIONAL

# docling 2.135.0 warns about fields of its own that it still reads.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# Written by hand from the document, so a fault shared by both readers cannot hide:
# id, part, defect class, zone, comparison, limit, unit, page.
EXPECTED = [
    ("4.1", "pcb1", "melt", ANY_ZONE, NONE, None, None, 3),
    ("4.2.1", "pcb1", "scratch", "A", GT, 1.0, Unit.MM, 3),
    ("4.2.2", "pcb1", "scratch", "B", GT, 2.0, Unit.MM, 3),
    ("4.3", "pcb1", "missing", ANY_ZONE, NONE, None, None, 3),
    ("4.4", "pcb1", "bent", ANY_ZONE, NONE, None, None, 3),
    ("5.1.1", "pcb4", "dirt", "A", GT, 0.5, Unit.MM, 4),
    ("5.1.2", "pcb4", "dirt", "B", GT, 1.0, Unit.MM, 4),
    ("5.1.3", "pcb4", "dirt", "C", GT, 2.0, Unit.MM, 4),
    ("5.2", "pcb4", "missing", ANY_ZONE, NONE, None, None, 4),
    ("5.3", "pcb4", "extra", ANY_ZONE, NONE, None, None, 4),
    ("5.4", "pcb4", "wrong place", ANY_ZONE, NONE, None, None, 5),
    ("5.5", "pcb4", "damage", ANY_ZONE, NONE, None, None, 5),
    ("5.6.1", "pcb4", "scratch", "A", GT, 1.0, Unit.MM, 5),
    ("5.6.2", "pcb4", "scratch", "B", GT, 2.0, Unit.MM, 5),
    ("5.6.3", "pcb4", "scratch", "C", GT, 3.0, Unit.MM, 5),
    ("5.7", "pcb4", "burnt", ANY_ZONE, NONE, None, None, 5),
]


@pytest.fixture(scope="module")
def parsed() -> ParsedPdf:
    """Read the tracked PDF with docling, once for the module.

    Returns:
        The PDF's blocks, page count and text.
    """
    return read_pdf(PDF)


@pytest.fixture(scope="module")
def from_pdf(parsed: ParsedPdf) -> Specification:
    """Extract the specification from the PDF's blocks.

    Returns:
        The specification as parsed from the PDF.
    """
    return extract_specification(parsed.blocks, pages=parsed.pages)


@pytest.fixture(scope="module")
def from_markdown() -> Specification:
    """Extract the specification from the Markdown source, which has no pages.

    Returns:
        The specification as written.
    """
    return extract_specification(read_markdown(MARKDOWN.read_text(encoding="utf-8")), pages=1)


def without_pages(specification: Specification) -> dict[str, object]:
    """Dump a specification with every page number removed.

    Args:
        specification: The specification.

    Returns:
        Its fields, comparable between a paged and an unpaged reading.
    """
    dumped = specification.model_dump(exclude={"pages"})
    for group in ("calibrations", "zones", "clauses"):
        for row in dumped[group]:
            del row["page"]
    return dumped


def test_the_pdf_gives_back_every_clause_zone_and_calibration_of_the_markdown(
    from_pdf: Specification, from_markdown: Specification
) -> None:
    """Ids, titles, classes, zones, limits, units, dispositions and source text all agree."""
    assert len(from_pdf.clauses) == len(from_markdown.clauses) == 16
    for parsed_clause, written in zip(from_pdf.clauses, from_markdown.clauses, strict=True):
        assert parsed_clause.model_dump(exclude={"page"}) == written.model_dump(exclude={"page"})
    assert without_pages(from_pdf) == without_pages(from_markdown)


def test_the_clause_table_is_the_one_written_by_hand(from_pdf: Specification) -> None:
    """Every clause has the id, class, zone, limit, unit and page read from the document by eye."""
    assert [
        (c.id, c.category, c.defect_class, c.zone, c.comparison, c.limit, c.unit, c.page)
        for c in from_pdf.clauses
    ] == EXPECTED


def test_each_clause_is_on_the_page_a_second_pdf_reader_finds_its_heading_on(
    from_pdf: Specification,
) -> None:
    """A second reader, pdfium's text layer, says which page prints each clause's heading."""
    document = pypdfium2.PdfDocument(PDF)
    texts = [page.get_textpage().get_text_bounded() for page in document]

    assert from_pdf.pages == len(texts)
    for clause in from_pdf.clauses:
        heading = f"{clause.heading_id} {clause.title}"
        pages = [number for number, text in enumerate(texts, start=1) if heading in text]
        assert pages == [clause.page], heading


def test_headings_arrive_at_the_level_of_their_numbers(parsed: ParsedPdf) -> None:
    """The title is level 1, a section level 2 and a clause level 3: none is flattened."""
    headings = [block for block in parsed.blocks if isinstance(block, Heading)]

    assert headings[0].level == 1
    assert {h.text: h.level for h in headings}["5 Acceptance criteria for part PCB4"] == 2
    assert {h.text: h.level for h in headings}["5.6 Scratch"] == 3
    assert sorted({h.level for h in headings}) == [1, 2, 3]
    assert len(headings) == 20


def test_the_tracked_clause_table_is_the_parse_of_the_tracked_pdf(
    from_pdf: Specification,
) -> None:
    """The JSON that later units read is exactly what `parse` gives for the PDF beside it."""
    assert read_clause_table(CLAUSE_TABLE) == from_pdf


def test_parsing_gives_the_specification_and_the_text_the_judge_reads(
    parsed: ParsedPdf, from_pdf: Specification
) -> None:
    """The one-call parse agrees with the two steps; the text holds the clauses' words."""
    assert parsed.pages == 6
    assert "5.6 Scratch" in parsed.text
    assert "> 3.0 mm" in parsed.text
    assert "Written for the Spec to Inspector entry" in parsed.text
    assert parsed.specification() == from_pdf


def test_a_file_that_is_not_a_pdf_is_refused(tmp_path: Path) -> None:
    """A missing file and a file docling cannot convert both raise the parser's error."""
    with pytest.raises(PdfError, match=r"missing\.pdf"):
        read_pdf(tmp_path / "missing.pdf")
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a PDF")
    with pytest.raises(PdfError, match=r"broken\.pdf"):
        read_pdf(broken)
