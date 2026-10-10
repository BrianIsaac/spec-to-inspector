"""A document as a flat run of blocks: what both readers of a specification produce.

The PDF reader (docling) and the Markdown reader each turn their document
into the same three kinds of block, in reading order, and one extraction
turns blocks into clauses. Text is held with single spaces, so a line break
in a PDF and a line break in a Markdown source cannot make two readings
differ.
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def fold(text: str) -> str:
    """Fold a text's white space to single spaces and trim its ends.

    Args:
        text: Text as a reader produced it.

    Returns:
        The same words separated by single spaces.
    """
    return " ".join(text.split())


def _fold_rows(rows: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
    """Fold the white space of every cell of a table.

    Args:
        rows: The table's rows of cells.

    Returns:
        The rows with each cell folded.
    """
    return tuple(tuple(fold(cell) for cell in row) for row in rows)


Folded = Annotated[str, AfterValidator(fold)]
PageNumber = Annotated[int, Field(ge=1)]


class Heading(BaseModel):
    """A heading, with the level the reader found it at.

    Attributes:
        level: 1 for the document's title, 2 for a section, 3 for a clause.
        text: The heading as printed, its number included.
        page: The page it is printed on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Annotated[int, Field(ge=1)]
    text: Folded
    page: PageNumber


class Paragraph(BaseModel):
    """A paragraph of running text.

    Attributes:
        text: The paragraph's text.
        page: The page it starts on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Folded
    page: PageNumber


class Table(BaseModel):
    """A table, as rows of cell texts with the header row first.

    Attributes:
        rows: The rows, each a tuple of cell texts.
        page: The page it starts on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: Annotated[tuple[tuple[str, ...], ...], AfterValidator(_fold_rows)]
    page: PageNumber


Block = Heading | Paragraph | Table
