"""A proportion with its 95% Wilson score interval.

Every share the bench reports is a count of an N, and the N is small (135,
65, 44), so each is given with an interval. The Wilson score interval is used
because it stays inside 0 and 1 and does not collapse to a point when the
count is 0 or N, as the normal approximation does.
"""

import math
from typing import Final

from pydantic import BaseModel, ConfigDict

Z_95: Final = 1.959964
"""The standard normal quantile for a two-sided 95% interval."""


class Proportion(BaseModel):
    """A count of an N, its share and the share's 95% Wilson score interval.

    Attributes:
        count: How many.
        n: Of how many.
        rate: The share, a fraction of 1; None when N is zero.
        low: The interval's lower bound; None when N is zero.
        high: The interval's upper bound; None when N is zero.
    """

    model_config = ConfigDict(frozen=True)

    count: int
    n: int
    rate: float | None
    low: float | None
    high: float | None


def wilson(count: int, n: int, *, z: float = Z_95) -> Proportion:
    """Give a count of an N with its Wilson score interval, without continuity correction.

    Args:
        count: How many.
        n: Of how many.
        z: The standard normal quantile of the interval; 95% by default.

    Returns:
        The proportion; with no rate and no interval when N is zero.

    Raises:
        ValueError: If the count is negative or above N.
    """
    if not 0 <= count <= n:
        msg = f"{count} of {n} is not a proportion"
        raise ValueError(msg)
    if n == 0:
        return Proportion(count=0, n=0, rate=None, low=None, high=None)
    rate = count / n
    denominator = 1 + z * z / n
    centre = (rate + z * z / (2 * n)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
    return Proportion(
        count=count,
        n=n,
        rate=rate,
        low=0.0 if count == 0 else max(0.0, centre - half),
        high=1.0 if count == n else min(1.0, centre + half),
    )
