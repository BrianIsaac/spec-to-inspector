"""The disposition rule: a clause's limit against a measurement, decided by code.

No number here comes from a language model. The judge names a defect class
and cites a clause; this module checks the citation against the clause and
the measured region, compares the clause's limit with the measurement, and
answers accept, reject or needs review with the reason in words. Anything it
cannot settle from the clause and the measurement goes to an engineer; it
never guesses.
"""

import operator
from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spec_to_inspector.measure.models import MeasuredRegion


class Comparison(StrEnum):
    """How a clause's limit is compared with the measurement."""

    GREATER = ">"
    GREATER_OR_EQUAL = ">="
    LESS = "<"
    LESS_OR_EQUAL = "<="
    UNCONDITIONAL = "unconditional"


class Outcome(StrEnum):
    """What becomes of a region."""

    ACCEPT = "accept"
    REJECT = "reject"
    NEEDS_REVIEW = "needs review"


class ReviewCause(StrEnum):
    """Why the rule could not settle a region itself."""

    MISSING_CLAUSE = "missing clause"
    CLASS_MISMATCH = "class mismatch"
    ZONE_MISMATCH = "zone mismatch"
    UNDEFINED_MEASUREMENT = "undefined measurement"


class Quantity(StrEnum):
    """The measurement a clause's unit asks for."""

    LONGEST_EXTENT = "longest extent"
    AREA = "area"


class Clause(BaseModel):
    """One clause of the specification, as far as the rule needs it.

    A clause reads "`disposition` if the measurement `comparison` `limit`
    `unit`", such as "reject if the longest extent > 0.5 mm"; when the
    comparison does not hold the other outcome follows. An unconditional
    clause gives its disposition whatever the size.

    Attributes:
        id: The clause number, such as "4.2.1".
        defect_class: The defect the clause covers, lower case, single spaced.
        zone: The zone the clause applies in; None for any zone.
        limit: The size the measurement is compared with; None if unconditional.
        unit: The limit's unit: "mm" is the longest extent, "mm2" the area.
        comparison: How the measurement is compared with the limit.
        disposition: The outcome when the comparison holds.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(min_length=1)
    defect_class: str = Field(min_length=1)
    zone: str | None = None
    limit: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    unit: str | None = None
    comparison: Comparison
    disposition: Literal[Outcome.ACCEPT, Outcome.REJECT]

    @field_validator("limit")
    @classmethod
    def _no_negative_zero(cls, value: float | None) -> float | None:
        """Turn floating point's negative zero into zero, so it never prints as "-0".

        Args:
            value: The limit as given.

        Returns:
            The same limit, with a negative zero made positive.
        """
        return value if value is None else value + 0.0

    @field_validator("defect_class")
    @classmethod
    def _one_spelling(cls, value: str) -> str:
        """Fold a class name to the one spelling classes are matched in.

        Args:
            value: The class name as written.

        Returns:
            The name in lower case with single spaces.
        """
        return _class_name(value)


class Disposition(BaseModel):
    """The rule's answer for one region, with everything the reason cites.

    Attributes:
        outcome: Accept, reject or needs review.
        reason: One sentence a manager reads.
        review_cause: Why an engineer must decide; None unless the outcome is
            needs review.
        clause_id: The clause applied, or the id cited if it does not exist.
        defect_class: The class the judge named, in the matched spelling.
        zone: The region's zone.
        quantity: The measurement compared; None if none was.
        measured: The measurement's value, copied from the region.
        limit: The clause's limit, copied from the clause.
        unit: The unit of both, "mm" or "mm2".
        comparison: The clause's comparison; None without a clause.
    """

    model_config = ConfigDict(frozen=True)

    outcome: Outcome
    reason: str
    review_cause: ReviewCause | None = None
    clause_id: str | None = None
    defect_class: str
    zone: str | None = None
    quantity: Quantity | None = None
    measured: float | None = None
    limit: float | None = None
    unit: str | None = None
    comparison: Comparison | None = None


_HOLDS: dict[Comparison, Callable[[float, float], bool]] = {
    Comparison.GREATER: operator.gt,
    Comparison.GREATER_OR_EQUAL: operator.ge,
    Comparison.LESS: operator.lt,
    Comparison.LESS_OR_EQUAL: operator.le,
}

# The words for a comparison that holds, and for one that does not.
_WORDS: dict[Comparison, tuple[str, str]] = {
    Comparison.GREATER: ("exceeds", "does not exceed"),
    Comparison.GREATER_OR_EQUAL: ("is at or above", "is below"),
    Comparison.LESS: ("is below", "is at or above"),
    Comparison.LESS_OR_EQUAL: ("does not exceed", "exceeds"),
}

# The unit's spellings, lower case without spaces, and how each is printed.
_UNITS: dict[str, tuple[Quantity, str, str]] = {
    "mm": (Quantity.LONGEST_EXTENT, "mm", "mm"),
    "mm2": (Quantity.AREA, "mm2", "mm²"),
    "mm^2": (Quantity.AREA, "mm2", "mm²"),
    "mm²": (Quantity.AREA, "mm2", "mm²"),
}

_OPPOSITE = {Outcome.ACCEPT: Outcome.REJECT, Outcome.REJECT: Outcome.ACCEPT}
_VERB = {Outcome.ACCEPT: "accepts", Outcome.REJECT: "rejects"}
_ENGINEER = "; an engineer must decide"
_BORDER = " (the region touches the image border, so its true size may be larger)"
_FEWEST_DECIMALS = 2
_MOST_DECIMALS = 17


def _class_name(value: str) -> str:
    """Fold a defect class name to lower case with single spaces.

    Args:
        value: The class name as written.

    Returns:
        The folded name, in which "Wrong  Place" and "wrong place" are equal.
    """
    return " ".join(value.split()).casefold()


def _plain(value: float) -> str:
    """Write a number exactly as given, without an exponent or trailing zeros.

    Args:
        value: The number.

    Returns:
        The shortest decimal that reads back as the same number.
    """
    text = format(Decimal(repr(value)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _measured_text(value: float, comparison: Comparison, limit: float) -> str:
    """Write a measurement so that the sentence cannot contradict the decision.

    Two decimals are the default. A measurement of 0.5004 against a limit of
    0.5 would then read "0.50 exceeds 0.5", so decimals are added until the
    printed figure stands to the limit as the exact one does.

    Args:
        value: The measurement.
        comparison: The clause's comparison.
        limit: The clause's limit.

    Returns:
        The measurement, rounded to the fewest decimals that keep its side of
        the limit.
    """
    holds = _HOLDS[comparison](value, limit)
    for decimals in range(_FEWEST_DECIMALS, _MOST_DECIMALS + 1):
        text = f"{value:.{decimals}f}"
        if _HOLDS[comparison](float(text), limit) == holds:
            return text
    return _plain(value)


class _Limit(NamedTuple):
    """A clause's limit, resolved to a measurement the inspector makes.

    Attributes:
        quantity: The measurement the unit asks for.
        unit: The unit as the decision records it, "mm" or "mm2".
        printed_unit: The unit as the reason prints it.
        value: The limit.
    """

    quantity: Quantity
    unit: str
    printed_unit: str
    value: float


def _limit_of(clause: Clause) -> _Limit | str:
    """Resolve a conditional clause's limit, or say why it cannot be measured against.

    Args:
        clause: A clause whose comparison is not unconditional.

    Returns:
        The limit with its quantity and unit, or the obstacle in words.
    """
    if clause.limit is None:
        return f"clause {clause.id} compares a size with a limit but states no limit"
    if clause.unit is None:
        return f"clause {clause.id} states no unit for its limit"
    known = _UNITS.get(clause.unit.replace(" ", "").casefold())
    if known is None:
        return (
            f"clause {clause.id} states its limit in '{clause.unit}', "
            "which the inspector does not measure"
        )
    return _Limit(*known, clause.limit)


def _mismatch(clause: Clause, region: MeasuredRegion, named: str) -> tuple[ReviewCause, str] | None:
    """Check that the clause cited is about this defect in this zone.

    Args:
        clause: The clause cited.
        region: The measured region.
        named: The class the judge named, folded.

    Returns:
        The cause and the reason in words if the clause does not apply, else None.
    """
    if named != clause.defect_class:
        return (
            ReviewCause.CLASS_MISMATCH,
            f"the defect was named '{named}', but clause {clause.id} covers "
            f"'{clause.defect_class}'",
        )
    if clause.zone is not None and clause.zone != region.zone:
        where = f"in zone {region.zone}" if region.zone is not None else "outside every zone"
        return (
            ReviewCause.ZONE_MISMATCH,
            f"clause {clause.id} applies in zone {clause.zone}, but the region lies {where}",
        )
    return None


def _unconditional(clause: Clause, region: MeasuredRegion, named: str) -> Disposition:
    """Apply a clause that gives its disposition whatever the size.

    Args:
        clause: An unconditional clause that applies to the region.
        region: The measured region.
        named: The class the judge named, folded.

    Returns:
        The clause's disposition; no measurement is cited, because none decides.
    """
    where = f"zone {clause.zone}" if clause.zone is not None else "any zone"
    return Disposition(
        outcome=clause.disposition,
        reason=(
            f"clause {clause.id} {_VERB[clause.disposition]} '{named}' in {where}, "
            "whatever its size"
        ),
        clause_id=clause.id,
        defect_class=named,
        zone=region.zone,
        comparison=clause.comparison,
    )


def _compared(clause: Clause, region: MeasuredRegion, named: str, limit: _Limit) -> Disposition:
    """Compare the region's measurement with the clause's limit.

    Args:
        clause: A conditional clause that applies to the region.
        region: The measured region.
        named: The class the judge named, folded.
        limit: The clause's limit, resolved.

    Returns:
        The clause's disposition if the comparison holds, the other outcome if not.
    """
    measured = (
        region.longest_extent_mm if limit.quantity is Quantity.LONGEST_EXTENT else region.area_mm2
    )
    holds = _HOLDS[clause.comparison](measured, limit.value)
    reason = (
        f"{limit.quantity} {_measured_text(measured, clause.comparison, limit.value)} "
        f"{limit.printed_unit} {_WORDS[clause.comparison][0 if holds else 1]} "
        f"the {_plain(limit.value)} {limit.printed_unit} limit of clause {clause.id}"
        + (f" in zone {clause.zone}" if clause.zone is not None else "")
        + (_BORDER if region.touches_border else "")
    )
    return Disposition(
        outcome=clause.disposition if holds else _OPPOSITE[clause.disposition],
        reason=reason,
        clause_id=clause.id,
        defect_class=named,
        zone=region.zone,
        quantity=limit.quantity,
        measured=measured,
        limit=limit.value,
        unit=limit.unit,
        comparison=clause.comparison,
    )


def _review(
    cause: ReviewCause,
    reason: str,
    *,
    clause: Clause | None,
    clause_id: str | None,
    named: str,
    region: MeasuredRegion,
) -> Disposition:
    """Build the answer for a region the rule cannot settle.

    Args:
        cause: Why it cannot be settled.
        reason: The cause in words, without the closing phrase.
        clause: The clause cited, if it exists.
        clause_id: The id cited.
        named: The class the judge named, folded.
        region: The measured region.

    Returns:
        A needs-review disposition; no measurement and no limit are cited,
        because none was compared.
    """
    return Disposition(
        outcome=Outcome.NEEDS_REVIEW,
        reason=reason + _ENGINEER,
        review_cause=cause,
        clause_id=clause_id,
        defect_class=named,
        zone=region.zone,
        comparison=clause.comparison if clause else None,
    )


def dispose(
    clause: Clause | None,
    region: MeasuredRegion,
    defect_class: str,
    *,
    cited_clause_id: str | None = None,
) -> Disposition:
    """Decide what becomes of a measured region under the clause cited for it.

    The checks run in a fixed order, and the first that fails sends the
    region to an engineer: the clause exists; the class named is the class
    the clause covers; the clause applies in the region's zone; the clause
    defines a measurement this inspector makes. Only then is the limit
    compared: the clause's disposition follows if the comparison holds, the
    other outcome if it does not.

    Args:
        clause: The clause cited, or None if the specification has no such clause.
        region: The measured region.
        defect_class: The defect class the judge named.
        cited_clause_id: The id that was cited, for the reason when no such
            clause exists.

    Returns:
        The outcome, its reason in words, and the figures the reason cites,
        each copied from the clause or the region.
    """
    named = _class_name(defect_class)
    if clause is None:
        cited = (
            f"clause {cited_clause_id} is not in the specification"
            if cited_clause_id is not None
            else "no clause was cited"
        )
        return _review(
            ReviewCause.MISSING_CLAUSE,
            f"{cited}, so no limit applies",
            clause=None,
            clause_id=cited_clause_id,
            named=named,
            region=region,
        )

    def review(cause: ReviewCause, reason: str) -> Disposition:
        return _review(
            cause, reason, clause=clause, clause_id=clause.id, named=named, region=region
        )

    mismatch = _mismatch(clause, region, named)
    if mismatch is not None:
        return review(*mismatch)
    if clause.comparison is Comparison.UNCONDITIONAL:
        return _unconditional(clause, region, named)
    limit = _limit_of(clause)
    if isinstance(limit, str):
        return review(ReviewCause.UNDEFINED_MEASUREMENT, limit)
    return _compared(clause, region, named, limit)
