"""Tests for the limit normaliser's grammar."""

import pytest

from spec_to_inspector.spec.limits import Comparison, Limit, LimitError, Unit, normalise_limit


@pytest.mark.parametrize(
    ("text", "comparison", "value", "unit"),
    [
        ("> 0.3 mm", Comparison.GT, 0.3, Unit.MM),
        (">0.3mm", Comparison.GT, 0.3, Unit.MM),
        (">= 0.3 mm", Comparison.GE, 0.3, Unit.MM),
        ("\N{GREATER-THAN OR EQUAL TO} 0.3 mm", Comparison.GE, 0.3, Unit.MM),
        ("< 2 mm", Comparison.LT, 2.0, Unit.MM),
        ("<= 2.50 mm", Comparison.LE, 2.5, Unit.MM),
        ("\N{LESS-THAN OR EQUAL TO} 2.50 mm", Comparison.LE, 2.5, Unit.MM),
        ("0.3 mm max", Comparison.GT, 0.3, Unit.MM),
        ("0.3 mm max.", Comparison.GT, 0.3, Unit.MM),
        ("0.3 mm maximum", Comparison.GT, 0.3, Unit.MM),
        ("max 0.3 mm", Comparison.GT, 0.3, Unit.MM),
        ("Maximum 0.3 mm", Comparison.GT, 0.3, Unit.MM),
        ("1.5 mm min", Comparison.LT, 1.5, Unit.MM),
        ("minimum 1.5 mm", Comparison.LT, 1.5, Unit.MM),
        ("  0.3\N{NO-BREAK SPACE}mm   MAX ", Comparison.GT, 0.3, Unit.MM),
        ("0 mm max", Comparison.GT, 0.0, Unit.MM),
        ("> 4 mm2", Comparison.GT, 4.0, Unit.MM2),
        ("4 mm\N{SUPERSCRIPT TWO} max", Comparison.GT, 4.0, Unit.MM2),
    ],
)
def test_a_bounded_limit_normalises_to_its_reject_condition(
    text: str, comparison: Comparison, value: float, unit: Unit
) -> None:
    """Each spelling of a bound gives the comparison that makes a measurement nonconforming."""
    assert normalise_limit(text) == Limit(comparison=comparison, value=value, unit=unit)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("300 um max", 0.3, Unit.MM),
        ("300 \N{MICRO SIGN}m max", 0.3, Unit.MM),
        ("300 \N{GREEK SMALL LETTER MU}m max", 0.3, Unit.MM),
        ("0.05 cm max", 0.5, Unit.MM),
        ("10 mil max", 0.254, Unit.MM),
        ("0.02 in max", 0.508, Unit.MM),
        ("0.02 inch max", 0.508, Unit.MM),
    ],
)
def test_a_length_is_converted_to_millimetres_exactly(text: str, value: float, unit: Unit) -> None:
    """Other length units become millimetres by decimal arithmetic, with no float noise."""
    assert normalise_limit(text) == Limit(comparison=Comparison.GT, value=value, unit=unit)


@pytest.mark.parametrize(
    "text",
    ["not permitted", "Not permitted", "NOT  PERMITTED", "none permitted", "not allowed"],
)
def test_a_prohibition_is_unconditional(text: str) -> None:
    """A prohibition carries no number and no unit."""
    assert normalise_limit(text) == Limit(
        comparison=Comparison.UNCONDITIONAL, value=None, unit=None
    )


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("0.3 mm", "no comparison"),
        ("> 0.3", "no unit"),
        ("0.3 max", "no unit"),
        ("> mm", "no number"),
        ("max", "no number"),
        ("> 0.3 parsecs", "unknown unit"),
        ("0.3 m max", "unknown unit"),
        ("> 0,3 mm", "decimal comma"),
        ("1,000 mm max", "decimal comma"),
        ("> -0.3 mm", "negative"),
        ("-0.3 mm max", "negative"),
        ("0.3 - 0.5 mm", "range"),
        ("0.3 to 0.5 mm max", "range"),
        ("> 0.3 mm max", "more than one comparison"),
        ("max 0.3 mm max", "more than one comparison"),
        ("0.3 mm max min", "does not match"),
        ("> 0.3 mm and < 1 mm", "does not match"),
        ("> 1e3 mm", "does not match"),
        ("> .3 mm", "does not match"),
        ("> 0.3. mm", "does not match"),
        ("=> 0.3 mm", "does not match"),
        ("not permitted > 0.3 mm", "does not match"),
        ("permitted", "does not match"),
        ("about 0.3 mm max", "does not match"),
    ],
)
def test_a_malformed_limit_is_refused_with_its_reason(text: str, reason: str) -> None:
    """Anything outside the grammar raises, naming the text and what is wrong with it."""
    with pytest.raises(LimitError) as caught:
        normalise_limit(text)

    assert reason in str(caught.value)
    assert repr(text) in str(caught.value)


def test_a_limit_error_is_a_value_error() -> None:
    """Callers that validate input can catch the standard exception."""
    with pytest.raises(ValueError, match="empty"):
        normalise_limit("")


@pytest.mark.parametrize(
    ("comparison", "value", "unit"),
    [
        (Comparison.UNCONDITIONAL, 0.3, Unit.MM),
        (Comparison.UNCONDITIONAL, None, Unit.MM),
        (Comparison.GT, None, None),
        (Comparison.GT, 0.3, None),
        (Comparison.GT, -0.3, Unit.MM),
        (Comparison.GT, float("inf"), Unit.MM),
        (Comparison.GT, float("nan"), Unit.MM),
    ],
)
def test_a_limit_is_either_unconditional_or_fully_bounded(
    comparison: Comparison, value: float | None, unit: Unit | None
) -> None:
    """The model refuses a number without a comparison, and a comparison without a number."""
    with pytest.raises(ValueError, match="limit"):
        Limit(comparison=comparison, value=value, unit=unit)


@pytest.mark.parametrize(
    ("limit", "text"),
    [
        (Limit(comparison=Comparison.GT, value=0.5, unit=Unit.MM), "> 0.5 mm"),
        (Limit(comparison=Comparison.LE, value=2.0, unit=Unit.MM2), "<= 2 mm2"),
        (Limit(comparison=Comparison.UNCONDITIONAL, value=None, unit=None), "not permitted"),
    ],
)
def test_a_limit_prints_in_the_grammar_it_was_read_from(limit: Limit, text: str) -> None:
    """The canonical spelling of a limit normalises back to the same limit."""
    assert str(limit) == text
    assert normalise_limit(text) == limit
