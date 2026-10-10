"""The limit normaliser: a limit as a specification prints it becomes a typed reject condition.

A limit states when a measured quantity is nonconforming. Whatever way the
document spells it, the normalised form reads `measurement <comparison> value`
in a canonical unit, so the disposition rule compares numbers and never text:

- `> 0.3 mm`, `>= 0.3 mm`, `< 0.3 mm`, `<= 0.3 mm` are taken as written;
- `0.3 mm max` (or `max 0.3 mm`, `maximum`, `max.`) names the largest
  conforming value, so it normalises to `> 0.3 mm`;
- `0.3 mm min` names the smallest conforming value, so it normalises to
  `< 0.3 mm`;
- `not permitted` (or `none permitted`, `not allowed`) is unconditional.

Lengths are converted to millimetres and areas are kept in square
millimetres, by decimal arithmetic. Anything outside this grammar is refused
with the reason: a limit is never guessed.
"""

import math
import re
import unicodedata
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator


class Comparison(StrEnum):
    """How a measurement is compared with a limit's value to find it nonconforming."""

    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    UNCONDITIONAL = "unconditional"


class Unit(StrEnum):
    """The canonical units a limit is held in."""

    MM = "mm"
    MM2 = "mm2"


class LimitError(ValueError):
    """A limit's text is outside the normaliser's grammar."""

    def __init__(self, text: str, reason: str) -> None:
        """Record the text and what is wrong with it.

        Args:
            text: The limit as it was written.
            reason: Why it cannot be normalised.
        """
        super().__init__(f"cannot normalise the limit {text!r}: {reason}")
        self.text = text
        self.reason = reason


class Limit(BaseModel):
    """A reject condition: a measurement is nonconforming when it compares so with the value.

    Attributes:
        comparison: The comparison that makes a measurement nonconforming, or
            unconditional when the defect is nonconforming at any size.
        value: The bound, in `unit`; absent when unconditional.
        unit: The canonical unit of `value`; absent when unconditional.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison: Comparison
    value: float | None
    unit: Unit | None

    @model_validator(mode="after")
    def _unconditional_or_bounded(self) -> Self:
        """Refuse a number without a comparison, and a comparison without a number.

        Returns:
            The limit unchanged.

        Raises:
            ValueError: If the three fields do not agree.
        """
        if self.comparison is Comparison.UNCONDITIONAL:
            if self.value is not None or self.unit is not None:
                msg = "an unconditional limit carries no value and no unit"
                raise ValueError(msg)
            return self
        if self.value is None or self.unit is None:
            msg = f"a limit compared with {self.comparison.value!r} needs a value and a unit"
            raise ValueError(msg)
        if not math.isfinite(self.value) or self.value < 0:
            msg = f"a limit's value must be finite and not negative, got {self.value!r}"
            raise ValueError(msg)
        return self

    def __str__(self) -> str:
        """Spell the limit in the grammar `normalise_limit` reads."""
        if self.comparison is Comparison.UNCONDITIONAL or self.value is None or self.unit is None:
            return "not permitted"
        return f"{self.comparison.value} {self.value:.12g} {self.unit.value}"


UNCONDITIONAL_PHRASES: Final = frozenset(
    {"not permitted", "none permitted", "not allowed", "none allowed", "not acceptable"}
)

_MU: Final = "\N{GREEK SMALL LETTER MU}"
_EN_DASH: Final = "\N{EN DASH}"

# Multipliers to the canonical unit, keyed by the unit as written after NFKC folding
# (which turns the micro sign into the Greek mu and a superscript two into a digit).
_UNITS: Final[dict[str, tuple[Decimal, Unit]]] = {
    "mm": (Decimal(1), Unit.MM),
    "um": (Decimal("0.001"), Unit.MM),
    f"{_MU}m": (Decimal("0.001"), Unit.MM),
    "cm": (Decimal(10), Unit.MM),
    "mil": (Decimal("0.0254"), Unit.MM),
    "in": (Decimal("25.4"), Unit.MM),
    "inch": (Decimal("25.4"), Unit.MM),
    "mm2": (Decimal(1), Unit.MM2),
}

_BOUND: Final = r"maximum|max\.?|minimum|min\.?"
_GRAMMAR: Final = re.compile(
    rf"""
    (?P<symbol>>=|<=|>|<)?\s*
    (?P<before>{_BOUND})?\s*
    (?P<sign>-)?\s*
    (?P<value>\d+(?:\.\d+)?)?\s*
    (?P<unit>(?!(?:{_BOUND})(?:\s|$))[a-z{_MU}]+2?)?\s*
    (?P<after>{_BOUND})?
    """,
    re.VERBOSE,
)
_DECIMAL_COMMA: Final = re.compile(r"\d\s*,\s*\d")
_RANGE: Final = re.compile(rf"\d\s*[a-z{_MU}]*\s*(?:-|{_EN_DASH}|\bto\b)\s*\d")


def _fold(text: str) -> str:
    """Fold a limit's text to the form the grammar is written in.

    Args:
        text: The limit as written.

    Returns:
        The text in lower case, with compatibility characters folded, the
        comparison signs in ASCII and runs of white space as single spaces.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    folded = folded.replace("\N{GREATER-THAN OR EQUAL TO}", ">=").replace(
        "\N{LESS-THAN OR EQUAL TO}", "<="
    )
    return " ".join(folded.split())


def _bound_comparison(word: str) -> Comparison:
    """Give the reject comparison a bound word implies.

    Args:
        word: A matched bound word, such as `max` or `minimum`.

    Returns:
        Greater-than for a maximum, less-than for a minimum.
    """
    return Comparison.GT if word.startswith("max") else Comparison.LT


def normalise_limit(text: str) -> Limit:
    """Normalise a limit as a specification prints it.

    Args:
        text: The limit's text, for example `0.3 mm max`, `> 0.3 mm` or
            `not permitted`.

    Returns:
        The reject condition, with a length in millimetres or an area in
        square millimetres.

    Raises:
        LimitError: If the text is outside the grammar; the message names the
            text and the reason.
    """
    folded = _fold(text)
    if not folded:
        raise LimitError(text, "empty")
    if folded in UNCONDITIONAL_PHRASES:
        return Limit(comparison=Comparison.UNCONDITIONAL, value=None, unit=None)
    if _DECIMAL_COMMA.search(folded):
        raise LimitError(
            text, "decimal comma or thousands separator; write the number with a point"
        )
    if _RANGE.search(folded):
        raise LimitError(text, "a range is not a limit; state one bound")

    match = _GRAMMAR.fullmatch(folded)
    comparisons = [match["symbol"], match["before"], match["after"]] if match is not None else []
    stated = [c for c in comparisons if c is not None]
    if match is None or (not stated and match["value"] is None):
        raise LimitError(
            text,
            "does not match the grammar (a comparison sign or max/min, a number, a unit; "
            "or 'not permitted')",
        )
    if match["sign"] is not None:
        raise LimitError(text, "negative value")
    if match["value"] is None:
        raise LimitError(text, "no number")
    if match["unit"] is None:
        raise LimitError(text, "no unit")
    if match["unit"] not in _UNITS:
        known = ", ".join(sorted(_UNITS))
        raise LimitError(text, f"unknown unit {match['unit']!r} (known: {known})")
    if not stated:
        raise LimitError(text, "no comparison: a bare quantity does not say which side rejects")
    if len(stated) > 1:
        raise LimitError(text, "more than one comparison")

    comparison = (
        Comparison(match["symbol"]) if match["symbol"] is not None else _bound_comparison(stated[0])
    )
    factor, unit = _UNITS[match["unit"]]
    return Limit(comparison=comparison, value=float(Decimal(match["value"]) * factor), unit=unit)
