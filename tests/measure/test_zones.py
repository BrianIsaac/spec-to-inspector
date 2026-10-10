"""Tests for the zones a region touches, by overlap and by centroid."""

import numpy as np
import pytest

from spec_to_inspector.measure.models import Zone, ZoneMap, ZoneOverlap
from spec_to_inspector.measure.zones import touched_zones

_LEFT = Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=0.5, y_max=1.0)
_RIGHT = Zone(id="B", rank=2, x_min=0.5, y_min=0.0, x_max=1.0, y_max=1.0)
_HALVES = ZoneMap(zones=(_RIGHT, _LEFT))


def _touched(pixels: np.ndarray, zone_map: ZoneMap) -> tuple[ZoneOverlap, ...]:
    """Treat the whole mask as one region's bounding box and find its zones."""
    rows, columns = np.nonzero(pixels)
    height, width = pixels.shape
    centroid = ((columns.mean() + 0.5) / width, (rows.mean() + 0.5) / height)
    return touched_zones(
        pixels, origin_px=(0, 0), mask_size_px=(width, height), centroid=centroid, zone_map=zone_map
    )


def _blank(height: int = 20, width: int = 40) -> np.ndarray:
    return np.zeros((height, width), dtype=np.bool_)


def test_a_region_inside_one_zone_is_in_that_zone() -> None:
    """All of its area and its centroid lie in the lenient zone, and nothing in the strict one."""
    pixels = _blank()
    pixels[5:10, 25:35] = True

    assert _touched(pixels, _HALVES) == (
        ZoneOverlap(zone_id="B", rank=2, overlap_fraction=1.0, contains_centroid=True),
    )


def test_a_region_straddling_two_zones_lists_the_stricter_first() -> None:
    """Two columns of twelve reach into the strict zone; that is enough for it to come first."""
    pixels = _blank()
    pixels[5:10, 18:30] = True

    touched = _touched(pixels, _HALVES)

    assert [overlap.zone_id for overlap in touched] == ["A", "B"]
    assert touched[0].overlap_fraction == pytest.approx(2 / 12)
    assert touched[1].overlap_fraction == pytest.approx(10 / 12)
    assert (touched[0].contains_centroid, touched[1].contains_centroid) == (False, True)


def test_a_region_that_only_abuts_a_zone_does_not_touch_it() -> None:
    """Its first column starts where the strict zone ends: no shared area, so no claim."""
    pixels = _blank()
    pixels[5:10, 20:30] = True

    assert [overlap.zone_id for overlap in _touched(pixels, _HALVES)] == ["B"]


def test_a_centroid_inside_a_zone_counts_without_any_overlap() -> None:
    """A ring around a strict island has its centre on the island, so the island's zone applies."""
    island = Zone(id="A", rank=1, x_min=0.45, y_min=0.4, x_max=0.55, y_max=0.6)
    board = Zone(id="B", rank=2, x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
    pixels = _blank()
    pixels[4:16, 12:28] = True
    pixels[6:14, 14:26] = False

    touched = _touched(pixels, ZoneMap(zones=(board, island)))

    assert touched == (
        ZoneOverlap(zone_id="A", rank=1, overlap_fraction=0.0, contains_centroid=True),
        ZoneOverlap(zone_id="B", rank=2, overlap_fraction=1.0, contains_centroid=True),
    )


def test_a_region_outside_every_zone_touches_none() -> None:
    """Zones need not cover the board; a region in the gap has no zone."""
    corner = Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=0.25, y_max=0.25)
    pixels = _blank()
    pixels[10:15, 30:35] = True

    assert _touched(pixels, ZoneMap(zones=(corner,))) == ()


def test_no_zones_means_no_zone() -> None:
    """An empty map answers for any region."""
    pixels = _blank()
    pixels[0, 0] = True

    assert _touched(pixels, ZoneMap()) == ()


def test_a_zone_edge_that_binary_fractions_cannot_hold_does_not_leak() -> None:
    """0.3 of 100 pixels is column 30 on paper and 30.000000000000004 in floating point."""
    narrow = Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=0.3, y_max=1.0)
    pixels = _blank(height=10, width=100)
    pixels[2:4, 30:40] = True

    assert _touched(pixels, ZoneMap(zones=(narrow,))) == ()


def test_a_pixel_cut_by_a_zone_edge_counts_for_the_part_inside() -> None:
    """A zone ending at 0.25 of ten pixels cuts column 2 in half."""
    quarter = Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=0.25, y_max=1.0)
    pixels = _blank(height=4, width=10)
    pixels[1, 2] = True

    (overlap,) = _touched(pixels, ZoneMap(zones=(quarter,)))

    assert overlap.overlap_fraction == pytest.approx(0.5)


def test_overlapping_zones_are_both_listed() -> None:
    """Where the specification draws one zone over another, the region is in both."""
    inner = Zone(id="keep-out", rank=1, x_min=0.25, y_min=0.25, x_max=0.75, y_max=0.75)
    outer = Zone(id="board", rank=2, x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
    pixels = _blank()
    pixels[8:12, 15:25] = True

    touched = _touched(pixels, ZoneMap(zones=(outer, inner)))

    assert [(overlap.zone_id, overlap.overlap_fraction) for overlap in touched] == [
        ("keep-out", 1.0),
        ("board", 1.0),
    ]


def test_the_region_box_is_placed_by_its_origin() -> None:
    """The same pixels at another origin are a region somewhere else on the board."""
    region = np.ones((5, 10), dtype=np.bool_)

    def at(x: int) -> list[str]:
        centroid = ((x + 5) / 40, 7.5 / 20)
        touched = touched_zones(
            region, origin_px=(x, 5), mask_size_px=(40, 20), centroid=centroid, zone_map=_HALVES
        )
        return [overlap.zone_id for overlap in touched]

    assert at(2) == ["A"]
    assert at(15) == ["A", "B"]
    assert at(28) == ["B"]


def test_a_centroid_exactly_on_a_zone_edge_is_in_the_zone() -> None:
    """On the line between two zones the centroid counts for both, so the stricter applies."""
    pixels = _blank()
    pixels[5:10, 20:30] = True
    pixels[12:17, 10:20] = True

    touched = _touched(pixels, _HALVES)

    assert [(overlap.zone_id, overlap.contains_centroid) for overlap in touched] == [
        ("A", True),
        ("B", True),
    ]


def test_a_centroid_on_the_edge_of_a_zone_it_does_not_overlap_still_counts() -> None:
    """Three pixels in a shallow V: their centre sits on the edge of a zone none of them enters."""
    sliver = Zone(id="A", rank=1, x_min=0.375, y_min=0.0, x_max=0.5, y_max=0.25)
    pixels = np.zeros((4, 4), dtype=np.bool_)
    pixels[0, 0] = pixels[1, 1] = pixels[0, 2] = True

    assert _touched(pixels, ZoneMap(zones=(sliver,))) == (
        ZoneOverlap(zone_id="A", rank=1, overlap_fraction=0.0, contains_centroid=True),
    )
