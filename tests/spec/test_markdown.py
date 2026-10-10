"""Tests for the Markdown reader of a specification's source."""

from spec_to_inspector.spec.blocks import Heading, Paragraph, Table
from spec_to_inspector.spec.markdown import FigureSource, figure_sources, read_markdown

SOURCE = """\
# A *small* specification

Document X-1. Written for
a test.

## 1 Scope

- **Size**: the longest `extent`.
- A second item.

![Zones of the board.](figures/zones.jpg "visa:pcb9/Data/Images/Normal/0001.JPG#zones")

---

### 1.1 Scratch

A scratch is a [linear](https://example.org) mark.

| Clause | Limit |
| --- | --- |
| 1.1.1 | 0.5 mm max |
| 1.1.2 | > 1.0 mm |

![A scratch.](figures/scratch.jpg "visa:pcb9/Data/Images/Anomaly/007.JPG#mask=2")
"""


def test_headings_paragraphs_and_tables_come_out_in_reading_order() -> None:
    """Every block is on page 1, with inline markup reduced to its text."""
    assert read_markdown(SOURCE) == [
        Heading(level=1, text="A small specification", page=1),
        Paragraph(text="Document X-1. Written for a test.", page=1),
        Heading(level=2, text="1 Scope", page=1),
        Paragraph(text="Size: the longest extent.", page=1),
        Paragraph(text="A second item.", page=1),
        Heading(level=3, text="1.1 Scratch", page=1),
        Paragraph(text="A scratch is a linear mark.", page=1),
        Table(
            rows=(("Clause", "Limit"), ("1.1.1", "0.5 mm max"), ("1.1.2", "> 1.0 mm")),
            page=1,
        ),
    ]


def test_a_figure_is_not_a_paragraph_but_is_listed_with_its_source() -> None:
    """An image standing alone is a figure: its file, caption and VisA source are kept."""
    assert figure_sources(SOURCE) == [
        FigureSource(
            path="figures/zones.jpg",
            caption="Zones of the board.",
            source="visa:pcb9/Data/Images/Normal/0001.JPG#zones",
        ),
        FigureSource(
            path="figures/scratch.jpg",
            caption="A scratch.",
            source="visa:pcb9/Data/Images/Anomaly/007.JPG#mask=2",
        ),
    ]
