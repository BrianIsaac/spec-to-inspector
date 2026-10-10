"""The clause schema: what a parsed specification is, typed and validated.

A specification declares, per part (a VisA category such as `pcb4`), a
calibration that turns pixels into millimetres, a few zones as rectangles in
normalised image coordinates, and numbered clauses. A clause is one row a
disposition can be decided from: one defect class, one zone (or any zone),
one limit (or none, when the defect rejects at any size). A defect class with
a limit per zone is one numbered heading (`5.6`) with a sub-clause per zone
(`5.6.1`, `5.6.2`); a class that rejects unconditionally is the heading
itself (`5.2`).

The table is validated as a whole, so that a defect class of a part resolves
to exactly one clause in every zone: the judge never meets two clauses for
one region, nor a zone the document forgot.
"""

from collections import Counter, defaultdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from spec_to_inspector.spec.limits import Comparison, Limit, Unit

ANY_ZONE: Final = "any"

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ClauseId = Annotated[str, StringConstraints(pattern=r"^\d+(\.\d+)+$")]
Category = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*$")]
DefectClass = Annotated[str, StringConstraints(pattern=r"^[a-z]+( [a-z]+)*$")]
ZoneName = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]*$")]
ClauseZone = Annotated[str, StringConstraints(pattern=r"^([A-Z][A-Z0-9]*|any)$")]
Page = Annotated[int, Field(ge=1)]
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Millimetres = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]


class Disposition(StrEnum):
    """What a clause orders when its limit is met."""

    REJECT = "reject"
    REVIEW = "review"


class Calibration(BaseModel):
    """The declared scale of a part's inspection image.

    The board does not fill the frame, so the scale comes from the imaged
    area, not from the board width alone. Anomaly maps are often resampled
    to a square, so the scale is given on each axis.

    Attributes:
        category: The part, as VisA names the category.
        board_width_mm: The board's nominal width, as the document declares it.
        image_width_mm: The width of the scene the full image width covers.
        image_height_mm: The height of the scene the full image height covers.
        page: The page of the document that declares it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Category
    board_width_mm: Millimetres
    image_width_mm: Millimetres
    image_height_mm: Millimetres
    page: Page

    @model_validator(mode="after")
    def _image_holds_the_board(self) -> Self:
        """Refuse an image narrower than the board it is said to show.

        Returns:
            The calibration unchanged.

        Raises:
            ValueError: If the imaged width is less than the board width.
        """
        if self.image_width_mm < self.board_width_mm:
            msg = (
                f"the imaged width {self.image_width_mm} mm is less than the board width "
                f"{self.board_width_mm} mm"
            )
            raise ValueError(msg)
        return self

    def mm_per_pixel(self, width_px: int, height_px: int) -> tuple[float, float]:
        """Give the scale of an image or mask of the whole frame.

        Args:
            width_px: The image's width in pixels.
            height_px: The image's height in pixels.

        Returns:
            Millimetres per pixel across and down.
        """
        return self.image_width_mm / width_px, self.image_height_mm / height_px


class Zone(BaseModel):
    """A rectangle of the inspection image, in normalised coordinates.

    The origin is the image's top-left corner, x runs right and y runs down,
    and both run from 0 to 1 over the full image.

    Attributes:
        category: The part the zone belongs to.
        name: The zone's letter, as clauses name it.
        title: What the zone covers, in the document's words.
        rank: Criticality, 1 the most critical; where zones overlap or a
            defect straddles them, the lowest rank applies.
        x0: Left edge.
        y0: Top edge.
        x1: Right edge.
        y1: Bottom edge.
        page: The page of the document that declares it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Category
    name: ZoneName
    title: Text
    rank: Annotated[int, Field(ge=1)]
    x0: Fraction
    y0: Fraction
    x1: Fraction
    y1: Fraction
    page: Page

    @model_validator(mode="after")
    def _corners_in_order(self) -> Self:
        """Refuse a rectangle with no area.

        Returns:
            The zone unchanged.

        Raises:
            ValueError: If a far edge is not beyond its near edge.
        """
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            msg = f"zone {self.name} is not a rectangle: its corners are out of order"
            raise ValueError(msg)
        return self

    def contains(self, x: float, y: float) -> bool:
        """Say whether a point lies in the zone, edges included.

        Args:
            x: The point's normalised horizontal position.
            y: The point's normalised vertical position.

        Returns:
            True if the point is inside the rectangle or on its edge.
        """
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


class Clause(BaseModel):
    """One row of the clause table: a disposition can be decided from it alone.

    Attributes:
        id: The clause number as printed, such as `5.6.1` or `5.2`.
        heading_id: The numbered heading the clause sits under: the clause
            itself, or its parent when it is a per-zone sub-clause.
        title: The heading's title.
        category: The part, as VisA names the category.
        defect_class: The defect type, as VisA spells it.
        zone: The zone's letter, or `any`.
        comparison: The comparison that makes a measurement nonconforming.
        limit: The bound, in `unit`; absent when unconditional.
        unit: `mm` for a limit on the longest extent, `mm2` for one on the
            area; absent when unconditional.
        disposition: What the clause orders when the limit is met.
        page: The page of the document the clause is printed on.
        source_text: The clause's requirement, in the document's words.
        limit_text: The limit as the document prints it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: ClauseId
    heading_id: ClauseId
    title: Text
    category: Category
    defect_class: DefectClass
    zone: ClauseZone
    comparison: Comparison
    limit: float | None
    unit: Unit | None
    disposition: Disposition
    page: Page
    source_text: Text
    limit_text: Text

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Check the limit's three fields agree and the clause sits under its heading.

        Returns:
            The clause unchanged.

        Raises:
            ValueError: If the limit is half stated, or the numbering does
                not put the clause at or directly under its heading.
        """
        self.as_limit()
        under = self.id.startswith(f"{self.heading_id}.") and "." not in self.id.removeprefix(
            f"{self.heading_id}."
        )
        if self.id != self.heading_id and not under:
            msg = f"clause {self.id} is not heading {self.heading_id} nor directly under it"
            raise ValueError(msg)
        return self

    def as_limit(self) -> Limit:
        """Give the clause's limit as one typed reject condition.

        Returns:
            The comparison, value and unit together.
        """
        return Limit(comparison=self.comparison, value=self.limit, unit=self.unit)


class Specification(BaseModel):
    """A parsed specification: its calibrations, zones and clause table.

    Attributes:
        schema_version: The version of this format.
        title: The document's title.
        notice: The document's header line, saying what the document is.
        pages: The number of pages.
        calibrations: One per part.
        zones: The zones of every part.
        clauses: The clause table, in document order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    title: Text
    notice: Text
    pages: Page
    calibrations: tuple[Calibration, ...]
    zones: tuple[Zone, ...]
    clauses: tuple[Clause, ...]

    @model_validator(mode="after")
    def _judgeable(self) -> Self:
        """Check the table as a whole can be judged against.

        Returns:
            The specification unchanged.

        Raises:
            ValueError: With every inconsistency found.
        """
        problems = [
            *self._calibration_problems(),
            *self._zone_problems(),
            *self._clause_problems(),
            *self._coverage_problems(),
            *self._page_problems(),
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _calibration_problems(self) -> list[str]:
        """List parts with no calibration, or more than one."""
        declared = Counter(c.category for c in self.calibrations)
        used = {c.category for c in self.clauses} | {z.category for z in self.zones}
        return [
            f"part {category} has {declared[category]} calibrations, not one"
            for category in sorted(used | set(declared))
            if declared[category] != 1
        ]

    def _zone_problems(self) -> list[str]:
        """List zones declared twice and ranks shared within a part."""
        problems: list[str] = []
        names = Counter((z.category, z.name) for z in self.zones)
        ranks = Counter((z.category, z.rank) for z in self.zones)
        problems.extend(
            f"zone {name} of part {category} is declared more than once"
            for (category, name), n in names.items()
            if n > 1
        )
        problems.extend(
            f"rank {rank} is given to more than one zone of part {category}"
            for (category, rank), n in ranks.items()
            if n > 1
        )
        return problems

    def _clause_problems(self) -> list[str]:
        """List an empty table, repeated ids and zones no part has."""
        if not self.clauses:
            return ["the specification has no clauses"]
        problems = [
            f"clause {clause_id} appears more than once"
            for clause_id, n in Counter(c.id for c in self.clauses).items()
            if n > 1
        ]
        known = {(z.category, z.name) for z in self.zones}
        problems.extend(
            f"clause {c.id} names zone {c.zone!r}, which part {c.category} does not have"
            for c in self.clauses
            if c.zone != ANY_ZONE and (c.category, c.zone) not in known
        )
        return problems

    def _coverage_problems(self) -> list[str]:
        """List defect classes that do not resolve to exactly one clause in every zone."""
        problems: list[str] = []
        zones_by_part: dict[str, list[str]] = defaultdict(list)
        for z in sorted(self.zones, key=lambda z: z.rank):
            zones_by_part[z.category].append(z.name)
        covered: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        for c in self.clauses:
            covered[c.category, c.defect_class][c.zone] += 1
        for (category, defect_class), zones in covered.items():
            what = f"defect class {defect_class!r} of part {category}"
            problems.extend(
                f"{what} is covered more than once in zone {zone}"
                for zone, n in zones.items()
                if n > 1
            )
            if ANY_ZONE in zones and len(zones) > 1:
                problems.append(f"{what} has both a clause for any zone and clauses per zone")
            elif ANY_ZONE not in zones:
                problems.extend(
                    f"{what} has no clause for zone {zone}"
                    for zone in zones_by_part[category]
                    if zone not in zones
                )
        return problems

    def _page_problems(self) -> list[str]:
        """List anything placed on a page beyond the document's last."""
        placed = [
            *((f"clause {c.id}", c.page) for c in self.clauses),
            *((f"zone {z.name} of part {z.category}", z.page) for z in self.zones),
            *((f"the calibration of part {c.category}", c.page) for c in self.calibrations),
        ]
        return [
            f"{what} is on page {page} of a {self.pages}-page document"
            for what, page in placed
            if page > self.pages
        ]

    def categories(self) -> tuple[str, ...]:
        """Give the parts the clause table covers, in document order.

        Returns:
            Each category once.
        """
        return tuple(dict.fromkeys(c.category for c in self.clauses))

    def defect_classes(self, category: str) -> tuple[str, ...]:
        """Give a part's defect classes, in document order.

        Args:
            category: The part.

        Returns:
            Each defect class the part has a clause for, once.
        """
        return tuple(dict.fromkeys(c.defect_class for c in self.clauses if c.category == category))

    def find(self, clause_id: str) -> Clause | None:
        """Find a clause by its printed number.

        Args:
            clause_id: The number, such as `5.6.1`.

        Returns:
            The clause, or None if the table has no such row.
        """
        return next((c for c in self.clauses if c.id == clause_id), None)

    def clauses_for(self, category: str, defect_class: str) -> tuple[Clause, ...]:
        """Give every clause of a defect class of a part.

        Args:
            category: The part.
            defect_class: The defect type, as VisA spells it.

        Returns:
            One clause when the class rejects in any zone, one per zone when
            it has limits per zone, none when the part has no such class.
        """
        return tuple(
            c for c in self.clauses if c.category == category and c.defect_class == defect_class
        )

    def resolve(self, category: str, defect_class: str, zone: str | None) -> Clause | None:
        """Find the one clause that governs a defect class in a zone.

        Args:
            category: The part.
            defect_class: The defect type, as VisA spells it.
            zone: The zone's letter, or None for a region in no zone.

        Returns:
            The clause for that zone, or the class's any-zone clause; None
            when the class is unknown, or has limits per zone and the region
            is in none of them.
        """
        candidates = self.clauses_for(category, defect_class)
        return next((c for c in candidates if c.zone in (zone, ANY_ZONE)), None)

    def calibration(self, category: str) -> Calibration | None:
        """Find a part's calibration.

        Args:
            category: The part.

        Returns:
            The calibration, or None for a part the document does not cover.
        """
        return next((c for c in self.calibrations if c.category == category), None)

    def zones_of(self, category: str) -> tuple[Zone, ...]:
        """Give a part's zones, the most critical first.

        Args:
            category: The part.

        Returns:
            The zones in rank order.
        """
        return tuple(
            sorted((z for z in self.zones if z.category == category), key=lambda z: z.rank)
        )


def write_clause_table(specification: Specification, path: Path) -> None:
    """Write a specification as JSON, creating the directory if needed.

    Args:
        specification: The parsed specification.
        path: Where to write it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(specification.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_clause_table(path: Path) -> Specification:
    """Read a specification written by `write_clause_table`, validating it again.

    Args:
        path: The JSON file.

    Returns:
        The specification.

    Raises:
        pydantic.ValidationError: If the file does not hold a valid specification.
    """
    return Specification.model_validate_json(path.read_text(encoding="utf-8"))
