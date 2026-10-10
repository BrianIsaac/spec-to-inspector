"""Plane geometry for measurement: the convex hull and the minimum-area rectangle.

Written here in double precision instead of taken from OpenCV, whose
`minAreaRect` works in single precision: a bar of known length has to come
back as exactly that length.
"""

from typing import NamedTuple

import numpy as np
import numpy.typing as npt

IntPoints = npt.NDArray[np.int64]
FloatPoints = npt.NDArray[np.float64]


class Rectangle(NamedTuple):
    """A rectangle at any angle.

    Attributes:
        corners: The four corners (x, y), in order around the rectangle.
        long_side: The length of the longer side.
        short_side: The length of the shorter side.
    """

    corners: tuple[
        tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]
    ]
    long_side: float
    short_side: float


def _turn(origin: tuple[int, int], first: tuple[int, int], second: tuple[int, int]) -> int:
    """Give the cross product of origin-to-first and origin-to-second.

    Args:
        origin: The shared start of both vectors.
        first: The end of the first vector.
        second: The end of the second vector.

    Returns:
        A positive number for a counter-clockwise turn, negative for clockwise,
        zero when the three points lie on one line.
    """
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (
        second[0] - origin[0]
    )


def _half_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Build one chain of the hull from points already in order along it.

    Args:
        points: The points, sorted along the chain's direction.

    Returns:
        The chain's vertices, without the last point (it starts the other chain).
    """
    chain: list[tuple[int, int]] = []
    for point in points:
        while len(chain) >= 2 and _turn(chain[-2], chain[-1], point) <= 0:
            chain.pop()
        chain.append(point)
    return chain[:-1]


def convex_hull(points: IntPoints) -> IntPoints:
    """Find the convex hull of integer points (Andrew's monotone chain).

    The arithmetic is on Python integers, so the hull is exact.

    Args:
        points: The points, one (x, y) pair per row.

    Returns:
        The hull's vertices in counter-clockwise order (with x right and y
        up), each once, without points along its sides; one vertex for a
        single point, two for points on a line.

    Raises:
        ValueError: If the array is not rows of pairs, or has no rows.
    """
    if points.ndim != 2 or points.shape[1] != 2:
        msg = f"points are rows of (x, y) pairs, got shape {points.shape}"
        raise ValueError(msg)
    if points.shape[0] == 0:
        msg = "a hull needs at least one point"
        raise ValueError(msg)
    unique = np.unique(points, axis=0)
    ordered = [(int(x), int(y)) for x, y in unique.tolist()]
    if len(ordered) == 1:
        return np.array(ordered, dtype=np.int64)
    hull = _half_hull(ordered) + _half_hull(ordered[::-1])
    return np.array(hull, dtype=np.int64)


def min_area_rectangle(hull: FloatPoints) -> Rectangle:
    """Find the smallest rectangle, at any angle, around a convex polygon.

    The smallest rectangle around a convex polygon has a side along one of the
    polygon's sides, so each side is tried in turn.

    Args:
        hull: The polygon's vertices in order, one (x, y) pair per row, in any
            unit; one or two vertices are allowed.

    Returns:
        The rectangle, its sides in the unit of the vertices.
    """
    edges = np.roll(hull, -1, axis=0) - hull
    lengths = np.hypot(edges[:, 0], edges[:, 1])
    edges, lengths = edges[lengths > 0], lengths[lengths > 0]
    if edges.shape[0] == 0:
        corner = (float(hull[0, 0]), float(hull[0, 1]))
        return Rectangle(corners=(corner, corner, corner, corner), long_side=0.0, short_side=0.0)

    along = edges / lengths[:, None]
    across = np.stack([-along[:, 1], along[:, 0]], axis=1)
    along_positions = hull @ along.T
    across_positions = hull @ across.T
    along_low, along_high = along_positions.min(axis=0), along_positions.max(axis=0)
    across_low, across_high = across_positions.min(axis=0), across_positions.max(axis=0)
    best = int(np.argmin((along_high - along_low) * (across_high - across_low)))

    u, v = along[best], across[best]
    corners = [
        (float(a * u[0] + b * v[0]), float(a * u[1] + b * v[1]))
        for a, b in (
            (along_low[best], across_low[best]),
            (along_high[best], across_low[best]),
            (along_high[best], across_high[best]),
            (along_low[best], across_high[best]),
        )
    ]
    sides = (
        float(along_high[best] - along_low[best]),
        float(across_high[best] - across_low[best]),
    )
    return Rectangle(
        corners=(corners[0], corners[1], corners[2], corners[3]),
        long_side=max(sides),
        short_side=min(sides),
    )
