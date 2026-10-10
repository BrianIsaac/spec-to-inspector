"""The Markdown reader: a specification's source as blocks, and its figures.

The demo specification is written in Markdown and printed to PDF. Reading
the source into the same blocks the PDF reader produces is what lets the
round-trip test say that the PDF was parsed back to exactly what was written.
A Markdown file has no pages, so every block is on page 1.
"""

from collections.abc import Sequence
from typing import Final

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.spec.blocks import Block, Heading, Paragraph, Table

_PAGE: Final = 1
_SPACES: Final = frozenset({"softbreak", "hardbreak"})


class FigureSource(BaseModel):
    """A figure of the specification and where its picture comes from.

    Attributes:
        path: The image file, relative to the Markdown source.
        caption: The caption printed under it.
        source: What the picture is built from, such as
            `visa:pcb4/Data/Images/Anomaly/015.JPG#mask=4`; empty when the
            image is not built.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    caption: str
    source: str


def markdown_parser() -> MarkdownIt:
    """Build the parser the specification's source is written for.

    Returns:
        CommonMark with pipe tables, and nothing typographic that would
        change a character between the source and the page.
    """
    return MarkdownIt("commonmark").enable("table")


def plain_text(inline: Token) -> str:
    """Reduce an inline token to the text a reader of the page sees.

    Args:
        inline: An inline token with its children.

    Returns:
        The text, without markup and without images.
    """
    parts: list[str] = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in _SPACES:
            parts.append(" ")
    return "".join(parts)


def is_figure(inline: Token) -> bool:
    """Say whether an inline token is an image standing alone.

    Args:
        inline: An inline token with its children.

    Returns:
        True if it holds images and nothing else but line breaks.
    """
    children = [child for child in inline.children or [] if child.type not in _SPACES]
    return bool(children) and all(child.type == "image" for child in children)


def _table(tokens: Sequence[Token]) -> Table:
    """Collect a table's cells row by row.

    Args:
        tokens: The tokens from `table_open` to `table_close`.

    Returns:
        The table, header row first.
    """
    rows: list[tuple[str, ...]] = []
    cells: list[str] = []
    for token in tokens:
        if token.type == "tr_open":
            cells = []
        elif token.type == "inline":
            cells.append(plain_text(token))
        elif token.type == "tr_close":
            rows.append(tuple(cells))
    return Table(rows=tuple(rows), page=_PAGE)


def read_markdown(text: str) -> list[Block]:
    """Read a Markdown source into blocks.

    Args:
        text: The Markdown source.

    Returns:
        Its headings, paragraphs (list items included) and tables in order;
        figures and rules are left out.
    """
    tokens = markdown_parser().parse(text)
    blocks: list[Block] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "table_open":
            end = next(i for i in range(index, len(tokens)) if tokens[i].type == "table_close")
            blocks.append(_table(tokens[index : end + 1]))
            index = end
        elif token.type == "heading_open":
            blocks.append(
                Heading(level=int(token.tag[1:]), text=plain_text(tokens[index + 1]), page=_PAGE)
            )
            index += 1
        elif token.type == "inline" and not is_figure(token):
            blocks.append(Paragraph(text=plain_text(token), page=_PAGE))
        index += 1
    return blocks


def figure_sources(text: str) -> list[FigureSource]:
    """List the figures a Markdown source shows.

    Args:
        text: The Markdown source.

    Returns:
        Each image with its file, caption and source, in order.
    """
    figures: list[FigureSource] = []
    for token in markdown_parser().parse(text):
        for child in token.children or []:
            if child.type == "image":
                figures.append(
                    FigureSource(
                        path=str(child.attrGet("src") or ""),
                        caption=child.content,
                        source=str(child.attrGet("title") or ""),
                    )
                )
    return figures
