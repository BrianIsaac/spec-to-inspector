"""Tests for measuring the connected regions of a mask, on masks of known geometry."""

import math
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pytest

from spec_to_inspector.measure.models import (
    CalibratedMask,
    Calibration,
    MeasuredRegion,
    Zone,
    ZoneMap,
)
from spec_to_inspector.measure.regions import label_regions, measure_regions
from spec_to_inspector.settings import Settings

_STRICT = Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=0.5, y_max=1.0)
_LENIENT = Zone(id="B", rank=2, x_min=0.5, y_min=0.0, x_max=1.0, y_max=1.0)
_HALVES = ZoneMap(zones=(_STRICT, _LENIENT))


def _mask(pixels: np.ndarray, board_width_mm: float = 64.0) -> CalibratedMask:
    """Calibrate a mask that is at its source image's own size."""
    height, width = pixels.shape
    calibration = Calibration(
        board_width_mm=board_width_mm, image_width_px=width, image_height_px=height
    )
    return CalibratedMask(pixels=pixels, calibration=calibration)


def _blank(height: int = 128, width: int = 256) -> np.ndarray:
    return np.zeros((height, width), dtype=np.bool_)


def _bar(
    shape: tuple[int, int], centre: tuple[float, float], size: tuple[float, float], degrees: float
) -> np.ndarray:
    """Rasterise a rectangle at an angle: the pixels whose centres lie inside it.

    Args:
        shape: The mask's rows and columns.
        centre: The rectangle's centre (x, y) in pixels.
        size: The rectangle's length and width in pixels.
        degrees: The angle of its length from the x axis.

    Returns:
        The mask.
    """
    rows, columns = np.mgrid[0 : shape[0], 0 : shape[1]]
    x = columns + 0.5 - centre[0]
    y = rows + 0.5 - centre[1]
    angle = math.radians(degrees)
    along = x * math.cos(angle) + y * math.sin(angle)
    across = -x * math.sin(angle) + y * math.cos(angle)
    return (np.abs(along) <= size[0] / 2) & (np.abs(across) <= size[1] / 2)


def test_a_30_by_6_pixel_bar_measures_exactly_its_length() -> None:
    """At 64 mm across 256 pixels the bar is 7.5 mm long, 1.5 mm wide and 11.25 mm2, exactly."""
    pixels = _blank()
    pixels[40:46, 100:130] = True

    (region,) = measure_regions(_mask(pixels))

    assert region.longest_extent_mm == 7.5
    assert region.shortest_extent_mm == 1.5
    assert region.area_px == 180
    assert region.area_mm2 == 11.25


@pytest.mark.parametrize("board_width_mm", [100.0, 87.3, 1.0, 123.456])
@pytest.mark.parametrize("corner", [(0, 0), (17, 93), (122, 226)])
def test_the_bar_is_exact_at_any_scale_and_anywhere(
    board_width_mm: float, corner: tuple[int, int]
) -> None:
    """The length is thirty pixels times the declared scale to the last bit, wherever it lies."""
    pixels = _blank()
    pixels[corner[0] : corner[0] + 6, corner[1] : corner[1] + 30] = True
    scale = board_width_mm / 256

    (region,) = measure_regions(_mask(pixels, board_width_mm))

    assert region.longest_extent_mm == 30 * scale
    assert region.shortest_extent_mm == 6 * scale
    assert region.area_mm2 == 180 * (scale * scale)


def test_an_upright_bar_measures_the_same_as_one_lying_down() -> None:
    """Six columns by thirty rows is still a bar 7.5 mm long."""
    pixels = _blank()
    pixels[40:70, 100:106] = True

    (region,) = measure_regions(_mask(pixels))

    assert (region.longest_extent_mm, region.shortest_extent_mm) == (7.5, 1.5)


@pytest.mark.parametrize("degrees", [5, 15, 30, 45, 60, 75, 90, 110, 135, 160])
def test_a_rotated_bar_measures_within_a_pixel_diagonal(degrees: float) -> None:
    """A pixel is a square, so its corner can stand out past a slanted edge.

    The marked squares reach at most half a pixel diagonal (0.71 of a pixel)
    beyond each end of the true bar, so a side reads up to one diagonal (1.41
    pixels) long; a pixel is in or out by its centre, so it can also read a
    fraction of a pixel short.
    """
    pixels = _bar((128, 256), centre=(128.3, 64.6), size=(30.0, 6.0), degrees=degrees)

    (region,) = measure_regions(_mask(pixels))

    long_px, short_px = region.longest_extent_mm / 0.25, region.shortest_extent_mm / 0.25
    assert 30.0 - 0.5 <= long_px <= 30.0 + math.sqrt(2)
    assert 6.0 - 0.5 <= short_px <= 6.0 + math.sqrt(2)
    assert region.area_mm2 / 0.0625 == pytest.approx(180.0, abs=12.0)


@pytest.mark.parametrize("degrees", [0, 30, 45, 90, 120])
def test_a_squashed_mask_still_measures_in_millimetres(degrees: float) -> None:
    """A bar on a 1500 by 1000 image, seen through a 250 by 250 mask, keeps its 20 by 4 mm.

    The mask's pixels are 0.4 mm wide and 0.267 mm tall. Measured in pixels
    the bar would change length as it turns; measured in millimetres it stays
    within one mask pixel's diagonal of its size, as on a mask with square pixels.
    """
    source = _bar((1000, 1500), centre=(700.0, 450.0), size=(300.0, 60.0), degrees=degrees)
    rows = (np.arange(250) * 4 + 2)[:, None]
    columns = (np.arange(250) * 6 + 3)[None, :]
    calibration = Calibration(board_width_mm=100.0, image_width_px=1500, image_height_px=1000)
    mask = CalibratedMask(pixels=source[rows, columns], calibration=calibration)

    (region,) = measure_regions(mask)

    assert mask.pixel_size_mm == pytest.approx((0.4, 4 / 15))
    source_pixel_mm = 100.0 / 1500
    diagonal_mm = math.hypot(*mask.pixel_size_mm)
    assert region.longest_extent_mm == pytest.approx(20.0, abs=diagonal_mm + source_pixel_mm)
    assert region.shortest_extent_mm == pytest.approx(4.0, abs=diagonal_mm + source_pixel_mm)
    assert region.area_mm2 == pytest.approx(80.0, rel=0.05)


def test_one_pixel_is_one_pixel_square() -> None:
    """The smallest region there is measures one pixel each way."""
    pixels = _blank()
    pixels[10, 20] = True

    (region,) = measure_regions(_mask(pixels))

    assert (region.longest_extent_mm, region.shortest_extent_mm, region.area_mm2) == (
        0.25,
        0.25,
        0.0625,
    )
    assert region.bbox_px == (20, 10, 21, 11)


def test_two_regions_stay_two() -> None:
    """A gap of one pixel keeps two bars apart, each with its own measurement."""
    pixels = _blank()
    pixels[40:46, 100:130] = True
    pixels[47:50, 100:110] = True

    regions = measure_regions(_mask(pixels))

    assert sorted(region.longest_extent_mm for region in regions) == [2.5, 7.5]
    assert sorted(region.area_px for region in regions) == [30, 180]
    assert len({region.label for region in regions}) == 2


def test_pixels_that_meet_at_a_corner_are_one_region() -> None:
    """Regions are 8-connected: a diagonal step does not split a thin slanted defect."""
    pixels = _blank()
    pixels[10:12, 10:12] = True
    pixels[12:14, 12:14] = True

    (region,) = measure_regions(_mask(pixels))

    assert region.area_px == 8
    assert region.bbox_px == (10, 10, 14, 14)


def test_an_empty_mask_has_no_regions() -> None:
    """Nothing marked, nothing measured."""
    assert measure_regions(_mask(_blank())) == ()


def test_a_region_touching_the_border_is_measured_and_flagged() -> None:
    """Up against the edge the bar still measures its visible size, and says it may be cut off."""
    pixels = _blank()
    pixels[0:6, 226:256] = True
    pixels[60:66, 100:130] = True

    regions = {region.bbox_px: region for region in measure_regions(_mask(pixels))}

    at_the_edge = regions[(226, 0, 256, 6)]
    inside = regions[(100, 60, 130, 66)]
    assert (at_the_edge.longest_extent_mm, at_the_edge.shortest_extent_mm) == (7.5, 1.5)
    assert at_the_edge.touches_border
    assert not inside.touches_border


@pytest.mark.parametrize(
    "box",
    [(0, 6, 50, 80), (122, 128, 50, 80), (50, 56, 0, 30), (50, 56, 226, 256)],
    ids=["top", "bottom", "left", "right"],
)
def test_each_border_is_a_border(box: tuple[int, int, int, int]) -> None:
    """Top, bottom, left and right all count."""
    pixels = _blank()
    pixels[box[0] : box[1], box[2] : box[3]] = True

    (region,) = measure_regions(_mask(pixels))

    assert region.touches_border


def test_a_full_mask_is_one_region_the_size_of_the_board() -> None:
    """Every pixel marked: one region, 64 by 32 mm, touching every border."""
    (region,) = measure_regions(_mask(np.ones((128, 256), dtype=np.bool_)))

    assert (region.longest_extent_mm, region.shortest_extent_mm) == (64.0, 32.0)
    assert region.area_mm2 == 64.0 * 32.0
    assert region.centroid == (0.5, 0.5)
    assert region.touches_border


def test_the_region_carries_its_box_its_centre_and_its_rectangle() -> None:
    """What the reject card draws comes with the measurement, in mask pixels."""
    pixels = _blank()
    pixels[40:46, 100:130] = True

    (region,) = measure_regions(_mask(pixels))

    assert region.bbox_px == (100, 40, 130, 46)
    assert region.centroid == pytest.approx((115 / 256, 43 / 128))
    assert sorted(region.rectangle_px) == pytest.approx(
        [(100.0, 40.0), (100.0, 46.0), (130.0, 40.0), (130.0, 46.0)]
    )


def test_the_rectangle_of_a_slanted_bar_follows_the_bar() -> None:
    """The rectangle's long side lies along the defect, not along the image."""
    pixels = _bar((128, 256), centre=(128.0, 64.0), size=(60.0, 6.0), degrees=30)

    (region,) = measure_regions(_mask(pixels))

    corners = np.array(region.rectangle_px)
    sides = [corners[1] - corners[0], corners[2] - corners[1]]
    long_side = max(sides, key=lambda side: float(np.hypot(*side)))
    slope = math.degrees(math.atan2(long_side[1], long_side[0])) % 180
    assert slope == pytest.approx(30.0, abs=3.0)


def test_labels_match_the_label_image() -> None:
    """A region's label picks its own pixels out of the label image, for the anomaly map's peak."""
    pixels = _blank()
    pixels[40:46, 100:130] = True
    pixels[80:90, 10:20] = True

    labels, count = label_regions(pixels)
    regions = measure_regions(_mask(pixels))

    assert count == 2
    assert labels.shape == pixels.shape
    assert np.array_equal(labels > 0, pixels)
    for region in regions:
        assert int((labels == region.label).sum()) == region.area_px


def test_specks_below_the_minimum_area_are_dropped() -> None:
    """A floor on the area removes single-pixel noise and leaves the labels of the rest alone."""
    pixels = _blank()
    pixels[3, 3] = True
    pixels[40:46, 100:130] = True
    pixels[100, 200:203] = True

    everything = measure_regions(_mask(pixels))
    without_specks = measure_regions(_mask(pixels), min_area_px=4)

    assert [region.area_px for region in everything] == [1, 180, 3]
    assert [region.area_px for region in without_specks] == [180]
    assert without_specks[0] == everything[1]


@pytest.mark.parametrize("floor", [0, -3])
def test_a_minimum_area_below_one_pixel_is_refused(floor: int) -> None:
    """There is no region smaller than a pixel to keep."""
    with pytest.raises(ValueError, match="at least 1"):
        measure_regions(_mask(_blank()), min_area_px=floor)


def test_regions_come_in_the_order_they_are_met_reading_the_mask() -> None:
    """Top to bottom, then left to right, by each region's first pixel; labels count from 1."""
    pixels = _blank()
    pixels[50:55, 200:210] = True
    pixels[10:15, 100:110] = True
    pixels[10:15, 20:30] = True

    regions = measure_regions(_mask(pixels))

    assert [region.label for region in regions] == [1, 2, 3]
    assert [region.bbox_px[:2] for region in regions] == [(20, 10), (100, 10), (200, 50)]


def test_without_a_zone_map_a_region_has_no_zone() -> None:
    """Zones are the specification's; with none given, none is claimed."""
    pixels = _blank()
    pixels[40:46, 100:130] = True

    (region,) = measure_regions(_mask(pixels))

    assert region.zone is None
    assert region.zones == ()


def _zone_of(columns: tuple[int, int]) -> MeasuredRegion:
    pixels = _blank()
    pixels[40:46, columns[0] : columns[1]] = True
    (region,) = measure_regions(_mask(pixels), _HALVES)
    return region


def test_a_region_in_one_zone_takes_that_zone() -> None:
    """Wholly in the strict half or wholly in the lenient half: no contest."""
    assert _zone_of((20, 50)).zone == "A"
    assert _zone_of((150, 180)).zone == "B"


def test_a_region_straddling_zones_takes_the_stricter() -> None:
    """One column over the line is enough: the strict zone's limit is the one that applies."""
    region = _zone_of((127, 157))

    assert region.zone == "A"
    assert [overlap.zone_id for overlap in region.zones] == ["A", "B"]
    assert region.zones[0].overlap_fraction == pytest.approx(1 / 30)
    assert region.zones[1].contains_centroid


def test_a_region_outside_every_zone_has_no_zone() -> None:
    """The specification left that part of the board unzoned, and the measurement says so."""
    pixels = _blank()
    pixels[40:46, 200:230] = True

    (region,) = measure_regions(_mask(pixels), ZoneMap(zones=(_STRICT,)))

    assert region.zone is None


def test_zones_are_the_same_at_any_mask_resolution() -> None:
    """Normalised zones do not care whether the mask is the image or a 256 pixel copy of it."""
    source = _blank(height=1000, width=1500)
    source[400:440, 700:780] = True
    small = source[2::4, 3::6]
    calibration = Calibration(board_width_mm=100.0, image_width_px=1500, image_height_px=1000)

    (full,) = measure_regions(CalibratedMask(pixels=source, calibration=calibration), _HALVES)
    (squashed,) = measure_regions(CalibratedMask(pixels=small, calibration=calibration), _HALVES)

    assert full.zone == squashed.zone == "A"
    assert squashed.centroid == pytest.approx(full.centroid, abs=0.01)
    assert squashed.longest_extent_mm == pytest.approx(full.longest_extent_mm, abs=0.4)


# The real masks, when fetched


def _real_mask(path: Path) -> CalibratedMask:
    """Read a VisA mask, mark every labelled pixel, and calibrate it at 1 mm per pixel."""
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    assert image is not None, path
    height, width = image.shape
    calibration = Calibration(
        board_width_mm=float(width), image_width_px=width, image_height_px=height
    )
    return CalibratedMask(pixels=image > 0, calibration=calibration)


@pytest.mark.data
@pytest.mark.parametrize("category", ["pcb1", "pcb2", "pcb3", "pcb4"])
def test_real_masks_measure_consistently(
    category: str, record_property: Callable[[str, object], None]
) -> None:
    """Every VisA ground-truth mask of a category keeps the invariants the synthetic masks do.

    Each marked pixel belongs to exactly one region; neighbours share a
    region; a region fits inside its rectangle, the rectangle inside the
    image; and OpenCV's own rectangle around the same pixel corners has the
    same area, to its single precision.
    """
    paths = sorted((Settings().visa_dir / category / "Data" / "Masks" / "Anomaly").glob("*.png"))
    assert len(paths) == 100, "run `spec-to-inspector data fetch` first"

    region_counts: list[int] = []
    longest_px: list[float] = []
    for path in paths:
        mask = _real_mask(path)
        labels, count = label_regions(mask.pixels)
        regions = measure_regions(mask)

        assert np.array_equal(labels > 0, mask.pixels)
        for near, far in (
            (labels[:, :-1], labels[:, 1:]),
            (labels[:-1, :], labels[1:, :]),
            (labels[:-1, :-1], labels[1:, 1:]),
            (labels[:-1, 1:], labels[1:, :-1]),
        ):
            touching = (near > 0) & (far > 0)
            assert np.array_equal(near[touching], far[touching]), path
        assert len(regions) == count
        assert sum(region.area_px for region in regions) == int(mask.pixels.sum())

        diagonal = math.hypot(mask.width_px, mask.height_px)
        for region in regions:
            assert 1.0 <= region.shortest_extent_mm <= region.longest_extent_mm <= diagonal
            rectangle_area = region.longest_extent_mm * region.shortest_extent_mm
            assert region.area_mm2 <= rectangle_area * (1 + 1e-9)
            rows, columns = np.nonzero(labels == region.label)
            corners = np.concatenate(
                [np.stack([columns + dx, rows + dy], axis=1) for dx in (0, 1) for dy in (0, 1)]
            )
            (_, (width, height), _) = cv2.minAreaRect(corners.astype(np.float32))
            assert rectangle_area == pytest.approx(width * height, rel=1e-3), path
            assert region.bbox_px[0] <= region.centroid[0] * mask.width_px <= region.bbox_px[2]
            assert region.bbox_px[1] <= region.centroid[1] * mask.height_px <= region.bbox_px[3]
            longest_px.append(region.longest_extent_mm)
        region_counts.append(count)

    summary = {
        "category": category,
        "masks": len(paths),
        "image_px": [mask.width_px, mask.height_px],
        "regions": sum(region_counts),
        "regions_per_mask_max": max(region_counts),
        "longest_extent_px_median": round(float(np.median(longest_px)), 1),
        "longest_extent_px_max": round(max(longest_px), 1),
    }
    record_property("real_masks", summary)
    print(summary)
