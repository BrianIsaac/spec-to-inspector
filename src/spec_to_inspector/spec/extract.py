"""Blocks to clauses: the one deterministic reading of a specification's structure.

The document's shape is fixed and checked, never guessed:

- the first block is the title, a level-1 heading; the paragraph after it is
  the notice saying what the document is;
- every other heading is numbered, and its level is its number's depth plus
  one (`5` at level 2, `5.6` at level 3), so a clause number that a reader
  put at the wrong level stops the parse;
- a section headed `Acceptance criteria for part <PART>` holds that part's
  clauses: each level-3 heading there states its requirement in prose and
  then in one requirement table (`Clause | Defect class | Zone | Limit |
  Disposition`), a row per clause;
- the calibration table (`Part | Board width (mm) | Imaged width (mm) |
  Imaged height (mm)`) and the zone table (`Part | Zone | Covers | x0 | y0 |
  x1 | y1`) may sit anywhere outside a clause.

Anything else (other tables, captions, text after a requirement table) is
not a requirement and is left alone.
"""

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel, ValidationError

from spec_to_inspector.spec.blocks import Block, Heading, Paragraph, Table
from spec_to_inspector.spec.limits import LimitError, normalise_limit
from spec_to_inspector.spec.schema import (
    ANY_ZONE,
    Calibration,
    Clause,
    Disposition,
    Specification,
    Zone,
)

CALIBRATION_HEADER: Final = ("part", "board width (mm)", "imaged width (mm)", "imaged height (mm)")
ZONE_HEADER: Final = ("part", "zone", "covers", "x0", "y0", "x1", "y1")
CLAUSE_HEADER: Final = ("clause", "defect class", "zone", "limit", "disposition")
DISPOSITIONS: Final = {
    "reject": Disposition.REJECT,
    "review": Disposition.REVIEW,
    "refer for review": Disposition.REVIEW,
}

_NUMBERED: Final = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<title>\S.*)$")
_CRITERIA: Final = re.compile(
    r"^acceptance criteria for part (?P<part>[a-z][a-z0-9]*)$", re.IGNORECASE
)
_PLAIN_NUMBER: Final = re.compile(r"^\d+(?:\.\d+)?$")


class SpecificationError(ValueError):
    """A document does not have the structure of a specification."""


@dataclass
class _OpenClause:
    """A clause heading whose prose and requirement table are being collected."""

    number: str
    title: str
    page: int
    category: str
    prose: list[str] = field(default_factory=list[str])
    tabled: bool = False


def _built[M: BaseModel](model: type[M], what: str, fields: dict[str, object]) -> M:
    """Build a schema model, turning a validation failure into a located error.

    Args:
        model: The model to build.
        what: What is being built, for the error.
        fields: The model's fields.

    Returns:
        The validated model.

    Raises:
        SpecificationError: If the fields are not valid, naming each fault.
    """
    try:
        return model.model_validate(fields)
    except ValidationError as error:
        faults = "; ".join(
            ": ".join(filter(None, (".".join(str(part) for part in fault["loc"]), fault["msg"])))
            for fault in error.errors()
        )
        raise SpecificationError(f"{what}: {faults}") from error


def _number(text: str, what: str) -> float:
    """Read a plain decimal number from a table cell.

    Args:
        text: The cell's text.
        what: What the number is, for the error.

    Returns:
        The number.

    Raises:
        SpecificationError: If the cell is not digits with an optional decimal point.
    """
    if not _PLAIN_NUMBER.fullmatch(text):
        raise SpecificationError(f"{what}: {text!r} is not a plain number")
    return float(text)


def _body_rows(table: Table, header: Sequence[str], what: str) -> Iterable[tuple[str, ...]]:
    """Give a table's rows after its header, checking each has the header's width.

    Args:
        table: The table.
        header: The expected header.
        what: What the table is, for the error.

    Returns:
        The body rows.

    Raises:
        SpecificationError: If there are no rows, or a row is ragged.
    """
    body = table.rows[1:]
    if not body:
        raise SpecificationError(f"{what} on page {table.page} has no rows")
    for index, row in enumerate(body, start=1):
        if len(row) != len(header):
            raise SpecificationError(
                f"row {index} of {what} on page {table.page} has {len(row)} cells, "
                f"not {len(header)} cells"
            )
    return body


def _kind(table: Table) -> tuple[str, ...] | None:
    """Recognise a table by its header row.

    Args:
        table: The table.

    Returns:
        The header it matches, or None for a table the extraction does not read.
    """
    header = tuple(cell.casefold() for cell in table.rows[0]) if table.rows else ()
    return next((h for h in (CALIBRATION_HEADER, ZONE_HEADER, CLAUSE_HEADER) if h == header), None)


class _Extraction:
    """The state of one pass over a document's blocks."""

    def __init__(self) -> None:
        """Start with nothing read."""
        self.calibrations: list[Calibration] = []
        self.zones: list[Zone] = []
        self.clauses: list[Clause] = []
        self._section: str | None = None
        self._category: str | None = None
        self._clause: _OpenClause | None = None
        self._ranks: Counter[str] = Counter()

    def read(self, block: Block) -> None:
        """Take the next block in reading order.

        Args:
            block: The block.

        Raises:
            SpecificationError: If the block does not fit the document's structure.
        """
        match block:
            case Heading():
                self._heading(block)
            case Paragraph():
                if self._clause is not None and not self._clause.tabled:
                    self._clause.prose.append(block.text)
            case Table():
                self._table(block)

    def finish(self) -> None:
        """Close the last clause.

        Raises:
            SpecificationError: If the last clause heading has no requirement table.
        """
        if self._clause is not None and not self._clause.tabled:
            raise SpecificationError(
                f"clause {self._clause.number} on page {self._clause.page} has no requirement table"
            )
        self._clause = None

    def _heading(self, heading: Heading) -> None:
        """Enter a section or open a clause.

        Args:
            heading: The heading.

        Raises:
            SpecificationError: If the heading is not numbered, sits at the
                wrong level, or is not under the current section.
        """
        self.finish()
        numbered = _NUMBERED.fullmatch(heading.text)
        if numbered is None:
            raise SpecificationError(
                f"heading {heading.text!r} on page {heading.page} is not numbered"
            )
        number, title = numbered["number"], numbered["title"]
        depth = number.count(".") + 1
        if heading.level != depth + 1:
            raise SpecificationError(
                f"heading {heading.text!r} on page {heading.page} is numbered at depth {depth}, "
                f"so it belongs at level {depth + 1}, but is printed at level {heading.level}"
            )
        if depth == 1:
            criteria = _CRITERIA.fullmatch(title)
            self._section = number
            self._category = criteria["part"].lower() if criteria is not None else None
            return
        if self._section is None or not number.startswith(f"{self._section}."):
            raise SpecificationError(
                f"heading {heading.text!r} on page {heading.page} is not under section "
                f"{self._section}"
            )
        if depth == 2 and self._category is not None:
            self._clause = _OpenClause(number, title, heading.page, self._category)

    def _table(self, table: Table) -> None:
        """Read a table as requirements, calibrations or zones, or leave it alone.

        Args:
            table: The table.

        Raises:
            SpecificationError: If a clause's first table is not its
                requirement table, or a requirement table is not under a clause.
        """
        kind = _kind(table)
        if self._clause is not None and not self._clause.tabled:
            if kind != CLAUSE_HEADER:
                raise SpecificationError(
                    f"clause {self._clause.number}: the first table under its heading, on page "
                    f"{table.page}, is not a requirement table (header {table.rows[:1]!r})"
                )
            self._requirements(self._clause, table)
            self._clause.tabled = True
        elif kind == CLAUSE_HEADER:
            raise SpecificationError(
                f"the requirement table on page {table.page} is outside a clause of a section "
                "of acceptance criteria for a part, or is the clause's second"
            )
        elif kind == CALIBRATION_HEADER:
            self._calibrations(table)
        elif kind == ZONE_HEADER:
            self._zones(table)

    def _requirements(self, clause: _OpenClause, table: Table) -> None:
        """Turn a requirement table's rows into clauses.

        Args:
            clause: The heading the table sits under.
            table: The requirement table.

        Raises:
            SpecificationError: If the clause has no prose, or a row's limit,
                disposition or fields cannot be read.
        """
        what = f"the requirement table of clause {clause.number}"
        if not clause.prose:
            raise SpecificationError(
                f"clause {clause.number} on page {clause.page} states no requirement in words "
                "before its table"
            )
        for clause_id, defect_class, zone, limit_text, disposition in _body_rows(
            table, CLAUSE_HEADER, what
        ):
            try:
                limit = normalise_limit(limit_text)
            except LimitError as error:
                raise SpecificationError(f"clause {clause_id}: {error}") from error
            if disposition.casefold() not in DISPOSITIONS:
                known = ", ".join(sorted(DISPOSITIONS))
                raise SpecificationError(
                    f"clause {clause_id}: unknown disposition {disposition!r} (known: {known})"
                )
            self.clauses.append(
                _built(
                    Clause,
                    f"clause {clause_id} under heading {clause.number}",
                    {
                        "id": clause_id,
                        "heading_id": clause.number,
                        "title": clause.title,
                        "category": clause.category,
                        "defect_class": defect_class.casefold(),
                        "zone": ANY_ZONE if zone.casefold() == ANY_ZONE else zone,
                        "comparison": limit.comparison,
                        "limit": limit.value,
                        "unit": limit.unit,
                        "disposition": DISPOSITIONS[disposition.casefold()],
                        "page": clause.page,
                        "source_text": " ".join(clause.prose),
                        "limit_text": limit_text,
                    },
                )
            )

    def _calibrations(self, table: Table) -> None:
        """Read a calibration table.

        Args:
            table: The calibration table.

        Raises:
            SpecificationError: If a cell is not a number or a row is not valid.
        """
        for part, board, width, height in _body_rows(
            table, CALIBRATION_HEADER, "the calibration table"
        ):
            what = f"the calibration of part {part} on page {table.page}"
            self.calibrations.append(
                _built(
                    Calibration,
                    what,
                    {
                        "category": part.lower(),
                        "board_width_mm": _number(board, what),
                        "image_width_mm": _number(width, what),
                        "image_height_mm": _number(height, what),
                        "page": table.page,
                    },
                )
            )

    def _zones(self, table: Table) -> None:
        """Read a zone table, ranking each part's zones in the order listed.

        Args:
            table: The zone table.

        Raises:
            SpecificationError: If a cell is not a number or a row is not valid.
        """
        for part, name, covers, *corners in _body_rows(table, ZONE_HEADER, "the zone table"):
            what = f"zone {name} of part {part} on page {table.page}"
            x0, y0, x1, y1 = (_number(corner, what) for corner in corners)
            self._ranks[part.lower()] += 1
            self.zones.append(
                _built(
                    Zone,
                    what,
                    {
                        "category": part.lower(),
                        "name": name,
                        "title": covers,
                        "rank": self._ranks[part.lower()],
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "page": table.page,
                    },
                )
            )


def extract_specification(blocks: Sequence[Block], *, pages: int) -> Specification:
    """Read a specification from a document's blocks.

    Args:
        blocks: The document's headings, paragraphs and tables, in reading order.
        pages: The document's page count.

    Returns:
        The validated specification.

    Raises:
        SpecificationError: If the document does not have a specification's
            structure, or its clause table cannot be judged against; the
            message says what is wrong and where.
    """
    if not blocks or not isinstance(blocks[0], Heading) or blocks[0].level != 1:
        raise SpecificationError("the document does not start with its title as a level-1 heading")
    if len(blocks) < 2 or not isinstance(blocks[1], Paragraph):
        raise SpecificationError(
            "the title is not followed by the notice paragraph saying what the document is"
        )
    extraction = _Extraction()
    for block in blocks[2:]:
        extraction.read(block)
    extraction.finish()
    return _built(
        Specification,
        "the specification",
        {
            "title": blocks[0].text,
            "notice": blocks[1].text,
            "pages": pages,
            "calibrations": tuple(extraction.calibrations),
            "zones": tuple(extraction.zones),
            "clauses": tuple(extraction.clauses),
        },
    )
