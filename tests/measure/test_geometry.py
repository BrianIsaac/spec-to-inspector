"""Tests for the convex hull and the minimum-area rectangle."""

import math

import cv2
import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from spec_to_inspector.measure.geometry import convex_hull, min_area_rectangle

_coordinate = st.integers(min_value=-200, max_value=200)
_point_sets = st.lists(st.tuples(_coordinate, _coordinate), min_size=1, max_size=40)


def _ints(points: list[tuple[int, int]]) -> np.ndarray:
    return np.array(points, dtype=np.int64).reshape(-1, 2)


def _rotated(points: np.ndarray, degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    return points @ rotation.T


def _cross(origin: np.ndarray, first: np.ndarray, second: np.ndarray) -> int:
    return int(
        (first[0] - origin[0]) * (second[1] - origin[1])
        - (first[1] - origin[1]) * (second[0] - origin[0])
    )


def test_the_hull_of_a_square_is_its_four_corners() -> None:
    """Points inside and along the sides are dropped; the corners stay, each once."""
    points = _ints([(0, 0), (4, 0), (4, 4), (0, 4), (2, 2), (2, 0), (4, 2), (1, 3), (0, 0)])

    hull = convex_hull(points)

    assert sorted(map(tuple, hull.tolist())) == [(0, 0), (0, 4), (4, 0), (4, 4)]


def test_the_hull_turns_one_way_all_the_way_round() -> None:
    """Every three consecutive vertices turn the same way, so the polygon is convex."""
    points = _ints([(0, 0), (6, 1), (8, 5), (5, 9), (1, 7), (3, 4), (4, 4), (-2, 3)])

    hull = convex_hull(points)

    turns = [_cross(hull[i - 2], hull[i - 1], hull[i]) for i in range(len(hull))]
    assert all(turn > 0 for turn in turns)


def test_the_hull_of_one_point_is_that_point() -> None:
    """A single point, however often repeated, is its own hull."""
    assert convex_hull(_ints([(3, 5), (3, 5)])).tolist() == [[3, 5]]


def test_the_hull_of_points_on_a_line_is_the_two_ends() -> None:
    """Collinear points have no area; the hull is the segment's ends."""
    hull = convex_hull(_ints([(0, 0), (1, 1), (2, 2), (5, 5)]))

    assert sorted(map(tuple, hull.tolist())) == [(0, 0), (5, 5)]


def test_points_that_are_not_pairs_are_refused() -> None:
    """The hull is of points in the plane."""
    with pytest.raises(ValueError, match="pairs"):
        convex_hull(np.zeros((3, 3), dtype=np.int64))


def test_no_points_have_no_hull() -> None:
    """An empty set is a caller's mistake, not an empty polygon."""
    with pytest.raises(ValueError, match="at least one"):
        convex_hull(np.zeros((0, 2), dtype=np.int64))


def test_an_axis_aligned_box_is_its_own_rectangle_exactly() -> None:
    """No rounding at all when the rectangle lies along the axes."""
    box = np.array([(0.0, 0.0), (30.0, 0.0), (30.0, 6.0), (0.0, 6.0)])

    rectangle = min_area_rectangle(box)

    assert rectangle.long_side == 30.0
    assert rectangle.short_side == 6.0
    assert sorted(rectangle.corners) == [(0.0, 0.0), (0.0, 6.0), (30.0, 0.0), (30.0, 6.0)]


@pytest.mark.parametrize("degrees", [0.0, 10.0, 33.3, 45.0, 60.0, 90.0, 123.0, 179.0])
def test_a_rotated_box_keeps_its_sides(degrees: float) -> None:
    """Turning a 30 by 6 box does not change the rectangle around it."""
    box = _rotated(np.array([(0.0, 0.0), (30.0, 0.0), (30.0, 6.0), (0.0, 6.0)]), degrees)

    rectangle = min_area_rectangle(box)

    assert rectangle.long_side == pytest.approx(30.0, abs=1e-9)
    assert rectangle.short_side == pytest.approx(6.0, abs=1e-9)


def test_a_rhombus_is_wrapped_along_its_side_not_its_diagonals() -> None:
    """The diagonals' box has area 8; the rectangle along a side has area 6.4, and wins."""
    rhombus = np.array([(2.0, 0.0), (0.0, 1.0), (-2.0, 0.0), (0.0, -1.0)])

    rectangle = min_area_rectangle(rhombus)

    assert rectangle.long_side == pytest.approx(8 / math.sqrt(5))
    assert rectangle.short_side == pytest.approx(4 / math.sqrt(5))


def test_a_segment_has_a_rectangle_with_no_width() -> None:
    """Two points give their distance as the long side and nothing as the short one."""
    rectangle = min_area_rectangle(np.array([(1.0, 1.0), (4.0, 5.0)]))

    assert rectangle.long_side == pytest.approx(5.0)
    assert rectangle.short_side == pytest.approx(0.0, abs=1e-12)


def test_a_point_has_a_rectangle_with_no_size() -> None:
    """One point is a rectangle of nothing, at that point."""
    rectangle = min_area_rectangle(np.array([(2.0, 3.0)]))

    assert (rectangle.long_side, rectangle.short_side) == (0.0, 0.0)
    assert set(rectangle.corners) == {(2.0, 3.0)}


@given(_point_sets)
def test_the_rectangle_holds_every_point_and_is_no_larger_than_the_upright_box(
    points: list[tuple[int, int]],
) -> None:
    """Whatever the points, none falls outside, and the upright box never beats the rectangle."""
    hull = convex_hull(_ints(points)).astype(np.float64)

    rectangle = min_area_rectangle(hull)

    corners = np.array(rectangle.corners)
    cloud = np.array(points, dtype=np.float64)
    sides = np.array([corners[1] - corners[0], corners[3] - corners[0]])
    longer = sides[int(np.argmax(np.hypot(sides[:, 0], sides[:, 1])))]
    if np.hypot(*longer) > 0:
        along = longer / np.hypot(*longer)
        for axis in (along, np.array([-along[1], along[0]])):
            assert (cloud @ axis).min() >= (corners @ axis).min() - 1e-6
            assert (cloud @ axis).max() <= (corners @ axis).max() + 1e-6
    else:
        assert np.ptp(cloud, axis=0).tolist() == [0.0, 0.0]
    upright = np.ptp(np.array(points, dtype=np.float64), axis=0)
    assert rectangle.long_side * rectangle.short_side <= upright[0] * upright[1] + 1e-6
    assert rectangle.long_side >= rectangle.short_side >= 0.0


def test_the_rectangle_agrees_with_opencv_on_scattered_points() -> None:
    """An independent implementation finds the same area, to its single precision."""
    generator = np.random.default_rng(20261010)
    for _ in range(200):
        points = generator.integers(-300, 300, size=(int(generator.integers(3, 60)), 2))

        rectangle = min_area_rectangle(convex_hull(points.astype(np.int64)).astype(np.float64))

        (_, (width, height), _) = cv2.minAreaRect(points.astype(np.float32))
        assert rectangle.long_side * rectangle.short_side == pytest.approx(width * height, rel=1e-3)
