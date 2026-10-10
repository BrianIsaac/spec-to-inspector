"""The written table that maps a VisA defect type to the clause that covers it.

The labelled set is not labelled by hand: VisA names the defect types of each
anomalous image, and this table says which numbered heading of the demo
specification covers each type (the plan's decision 8). The table was written
with the specification, before any model was run; it is kept here as data,
rendered into `eval/clause_mapping.md`, and checked against the clause table
and against the mask values VisA uses for the same types.
"""

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.ground_truth import VISA_MASK_VALUES
from spec_to_inspector.spec.schema import ANY_ZONE, Specification

PARTS: Final[tuple[str, ...]] = ("pcb1", "pcb4")
"""The parts the demo specification covers, and so the parts of the labelled set."""

TABLE_HEADER: Final = "| Part | VisA type | Mask value | Heading | Clause ids | Rule |"
_TABLE_RULE: Final = "| --- | --- | --- | --- | --- | --- |"


class MappingError(ValueError):
    """A defect type has no row in the table, or the table disagrees with its sources."""


class MappingRow(BaseModel):
    """One line of the table: a part's VisA defect type and the heading that covers it.

    Attributes:
        part: The part, as VisA names its category.
        visa_type: The defect type, spelled as `image_anno.csv` spells it.
        mask_value: The value VisA's masks give the type's pixels.
        heading_id: The numbered heading of the specification that covers it.
        heading_title: The heading's title.
        clauses: The heading's rows as (clause id, zone), the zone None for a
            row that holds in any zone.
        rule: What the rows say, in words.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    visa_type: str
    mask_value: int
    heading_id: str
    heading_title: str
    clauses: tuple[tuple[str, str | None], ...]
    rule: str

    @property
    def heading(self) -> str:
        """The heading as the table prints it: its number, then its title."""
        return f"{self.heading_id} {self.heading_title}"

    @property
    def clause_ids(self) -> tuple[str, ...]:
        """The ids of the heading's rows, in the document's order."""
        return tuple(clause_id for clause_id, _ in self.clauses)


def _row(
    part: str,
    visa_type: str,
    mask_value: int,
    heading_id: str,
    heading_title: str,
    zones: str,
    rule: str,
) -> MappingRow:
    """Build a row; a zoned heading's rows are numbered under it in the zones' order.

    Args:
        part: The part.
        visa_type: The VisA defect type.
        mask_value: The type's mask value.
        heading_id: The heading's number.
        heading_title: The heading's title.
        zones: The zones the heading has a row for, as letters; empty for a
            heading that is its own single row.
        rule: What the rows say.

    Returns:
        The row.
    """
    clauses: tuple[tuple[str, str | None], ...] = (
        tuple((f"{heading_id}.{number}", zone) for number, zone in enumerate(zones, start=1))
        if zones
        else ((heading_id, None),)
    )
    return MappingRow(
        part=part,
        visa_type=visa_type,
        mask_value=mask_value,
        heading_id=heading_id,
        heading_title=heading_title,
        clauses=clauses,
        rule=rule,
    )


CLAUSE_MAPPING: Final[tuple[MappingRow, ...]] = (
    _row("pcb1", "melt", 2, "4.1", "Stray or bridging solder", "", "reject, any zone"),
    _row("pcb1", "scratch", 3, "4.2", "Scratch", "AB", "reject over 1.0 mm, 2.0 mm"),
    _row("pcb1", "missing", 4, "4.3", "Missing component", "", "reject, any zone"),
    _row("pcb1", "bent", 1, "4.4", "Bent header pin", "", "reject, any zone"),
    _row("pcb4", "dirt", 7, "5.1", "Foreign material", "ABC", "reject over 0.5, 1.0, 2.0 mm"),
    _row("pcb4", "missing", 3, "5.2", "Missing component", "", "reject, any zone"),
    _row("pcb4", "extra", 5, "5.3", "Extra component or object", "", "reject, any zone"),
    _row("pcb4", "wrong place", 6, "5.4", "Misplaced component", "", "reject, any zone"),
    _row("pcb4", "damage", 4, "5.5", "Damaged component or board", "", "reject, any zone"),
    _row("pcb4", "scratch", 2, "5.6", "Scratch", "ABC", "reject over 1.0, 2.0, 3.0 mm"),
    _row("pcb4", "burnt", 1, "5.7", "Burn mark", "", "reject, any zone"),
)
"""The table, in the specification's order: one row per defect type per part."""

_BY_TYPE: Final[dict[tuple[str, str], MappingRow]] = {
    (row.part, row.visa_type): row for row in CLAUSE_MAPPING
}


def mapping_row(part: str, visa_type: str) -> MappingRow:
    """Find the table's row for a part's defect type.

    Args:
        part: The part.
        visa_type: The VisA defect type.

    Returns:
        The row.

    Raises:
        MappingError: If the table has no row for the type on that part.
    """
    row = _BY_TYPE.get((part, visa_type))
    if row is None:
        msg = f"the mapping table has no row for the defect type {visa_type!r} of part {part}"
        raise MappingError(msg)
    return row


def expected_headings(part: str, visa_types: Sequence[str]) -> tuple[str, ...]:
    """Map a part's defect types to the headings that cover them.

    Args:
        part: The part.
        visa_types: The VisA defect types, in any order.

    Returns:
        One heading id per type, in the order given.

    Raises:
        MappingError: If a type has no row in the table.
    """
    return tuple(mapping_row(part, visa_type).heading_id for visa_type in visa_types)


def render_mapping_table(rows: Sequence[MappingRow] = CLAUSE_MAPPING) -> str:
    """Lay the table out as Markdown, one line per row.

    Args:
        rows: The rows to print.

    Returns:
        The table, without a trailing newline.
    """
    lines = [TABLE_HEADER, _TABLE_RULE]
    for row in rows:
        clauses = ", ".join(
            clause_id if zone is None else f"{clause_id} ({zone})"
            for clause_id, zone in row.clauses
        )
        lines.append(
            f"| {row.part} | {row.visa_type} | {row.mask_value} | {row.heading} | {clauses} "
            f"| {row.rule} |"
        )
    return "\n".join(lines)


def mapping_problems(
    specification: Specification, rows: Sequence[MappingRow] = CLAUSE_MAPPING
) -> list[str]:
    """Say where the table disagrees with a clause table or with VisA's mask values.

    Args:
        specification: The parsed specification.
        rows: The table's rows.

    Returns:
        One sentence per disagreement; empty when the table is the clause
        table's own mapping from part and defect class to heading and rows.
    """
    problems: list[str] = []
    covered = {(row.part, row.visa_type) for row in rows}
    for row in rows:
        name = f"{row.part} {row.visa_type}"
        clauses = specification.clauses_for(row.part, row.visa_type)
        if not clauses:
            problems.append(f"{name}: the specification has no clause for the class")
            continue
        written = tuple((c.id, None if c.zone == ANY_ZONE else c.zone) for c in clauses)
        if written != row.clauses:
            problems.append(f"{name}: the specification's rows are {written}, not {row.clauses}")
        headings = {(c.heading_id, c.title) for c in clauses}
        if headings != {(row.heading_id, row.heading_title)}:
            problems.append(f"{name}: the specification's heading is {sorted(headings)}")
        if VISA_MASK_VALUES.get(row.part, {}).get(row.mask_value) != row.visa_type:
            problems.append(f"{name}: VisA's mask value {row.mask_value} is not that type")
    problems.extend(
        f"{clause.category} {clause.defect_class}: the table has no row for the class"
        for clause in specification.clauses
        if (clause.category, clause.defect_class) not in covered
    )
    return list(dict.fromkeys(problems))
