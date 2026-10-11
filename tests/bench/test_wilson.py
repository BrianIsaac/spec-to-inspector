"""Tests for the Wilson score interval the figures are given with."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from spec_to_inspector.bench.wilson import Proportion, wilson


def test_the_interval_is_wilsons_at_95_per_cent() -> None:
    """Known values: 81 of 135, and the textbook 10 of 20."""
    known = wilson(81, 135)
    assert (known.count, known.n) == (81, 135)
    assert known.rate == pytest.approx(0.6)
    assert known.low == pytest.approx(0.5157, abs=5e-5)
    assert known.high == pytest.approx(0.6788, abs=5e-5)
    half = wilson(10, 20)
    assert (half.low, half.high) == (
        pytest.approx(0.2993, abs=5e-5),
        pytest.approx(0.7007, abs=5e-5),
    )


def test_the_ends_stay_inside_zero_and_one_and_are_not_degenerate() -> None:
    """None of N still has an upper bound above zero, and all of N a lower bound below one."""
    none, every = wilson(0, 44), wilson(44, 44)
    assert none.low == 0.0
    assert none.high == pytest.approx(0.0803, abs=5e-5)
    assert every.high == 1.0
    assert every.low == pytest.approx(0.9197, abs=5e-5)


def test_nothing_counted_has_no_rate_and_no_interval() -> None:
    """A proportion of an empty set is not a number."""
    assert wilson(0, 0) == Proportion(count=0, n=0, rate=None, low=None, high=None)


def test_a_count_outside_its_n_is_refused() -> None:
    """Five of four is a bug upstream, not a proportion."""
    with pytest.raises(ValueError, match="5 of 4"):
        wilson(5, 4)
    with pytest.raises(ValueError, match="-1 of 4"):
        wilson(-1, 4)


@given(st.integers(1, 500).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_the_interval_always_holds_the_rate(pair: tuple[int, int]) -> None:
    """For any count of any N the bounds are ordered and hold the observed share."""
    count, n = pair
    found = wilson(count, n)
    assert found.rate is not None
    assert found.low is not None
    assert found.high is not None
    assert 0.0 <= found.low <= found.rate <= found.high <= 1.0
