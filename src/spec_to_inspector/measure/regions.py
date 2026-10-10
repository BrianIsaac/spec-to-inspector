"""Connected regions of a mask, each measured in millimetres and placed in its zone."""

import cv2
import numpy as np
import numpy.typing as npt

from spec_to_inspector.measure.geometry import convex_hull, min_area_rectangle
from spec_to_inspector.measure.models import (
    BoolArray,
    CalibratedMask,
    MeasuredRegion,
    ZoneMap,
)
from spec_to_inspector.measure.zones import touched_zones

LabelArray = npt.NDArray[np.int32]

# Pixels that meet only at a corner belong to one region, so a thin slanted
# defect is measured whole instead of as a string of fragments.
CONNECTIVITY = 8


def _label(pixels: BoolArray) -> tuple[LabelArray, npt.NDArray[np.int32]]:
    """Number the connected regions of a mask and box each one.

    Args:
        pixels: The mask, rows by columns.

    Returns:
        The label image, and one row (left, top, width, height, area) per
        region in label order, all in pixels.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        pixels.astype(np.uint8), connectivity=CONNECTIVITY, ltype=cv2.CV_32S
    )
    found = np.asarray(labels, dtype=np.int32)
    boxes = np.asarray(stats, dtype=np.int32)[1:]
    first_column = [
        left + int(np.argmax(found[top, left : left + width] == number))
        for number, (left, top, width, _, _) in enumerate(boxes.tolist(), start=1)
    ]
    reading_order = np.lexsort((np.array(first_column, dtype=np.int64), boxes[:, 1]))
    renumber = np.zeros(count, dtype=np.int32)
    renumber[reading_order + 1] = np.arange(1, count, dtype=np.int32)
    return renumber[found], boxes[reading_order]


def label_regions(pixels: BoolArray) -> tuple[LabelArray, int]:
    """Number the connected regions of a mask.

    Regions are numbered from 1 in the order their first pixel is met reading
    the mask top to bottom and, within a row, left to right; the order is this
    function's own, not the labelling library's.

    Args:
        pixels: The mask, rows by columns.

    Returns:
        The label image (0 for background, the region's number elsewhere) and
        the number of regions.
    """
    labels, boxes = _label(pixels)
    return labels, int(boxes.shape[0])


def _outline_corners(region: BoolArray) -> npt.NDArray[np.int64]:
    """Give the pixel corners that can lie on a region's convex hull.

    A pixel is a unit square, not a point: measuring between pixel centres
    would make a 30 pixel bar 29 long. Only the first and the last pixel of
    each row can reach the hull, so their corners are enough.

    Args:
        region: The region's pixels within its bounding box; every row holds
            at least one, as a connected region's rows do.

    Returns:
        The corners, one (x, y) pair per row, relative to the bounding box.
    """
    height, width = region.shape
    first = region.argmax(axis=1).astype(np.int64)
    past_last = width - region[:, ::-1].argmax(axis=1).astype(np.int64)
    top = np.arange(height, dtype=np.int64)
    return np.concatenate(
        [np.stack([x, y], axis=1) for x in (first, past_last) for y in (top, top + 1)]
    )


def _measure(
    region: BoolArray,
    *,
    label: int,
    origin_px: tuple[int, int],
    mask: CalibratedMask,
    zone_map: ZoneMap,
) -> MeasuredRegion:
    """Measure one region.

    The minimum-area rectangle is found in millimetres, not pixels, so a mask
    whose pixels are not square (an image resized without keeping its aspect
    ratio) still gives the true long side of a slanted defect.

    Args:
        region: The region's pixels within its bounding box.
        label: The region's number in the label image.
        origin_px: The bounding box's top-left pixel (x, y) in the mask.
        mask: The mask the region belongs to.
        zone_map: The board's zones.

    Returns:
        The region's measurements and its zone.
    """
    height, width = region.shape
    left, top = origin_px
    x_mm, y_mm = mask.pixel_size_mm
    area_px = int(np.count_nonzero(region))

    hull = convex_hull(_outline_corners(region))
    rectangle = min_area_rectangle(hull.astype(np.float64) * np.array([x_mm, y_mm]))
    corners = [(x / x_mm + left, y / y_mm + top) for x, y in rectangle.corners]

    across = np.arange(width, dtype=np.float64) + 0.5
    down = np.arange(height, dtype=np.float64) + 0.5
    centroid = (
        (float(region.sum(axis=0, dtype=np.float64) @ across) / area_px + left) / mask.width_px,
        (float(region.sum(axis=1, dtype=np.float64) @ down) / area_px + top) / mask.height_px,
    )
    zones = touched_zones(
        region,
        origin_px=origin_px,
        mask_size_px=(mask.width_px, mask.height_px),
        centroid=centroid,
        zone_map=zone_map,
    )
    return MeasuredRegion(
        label=label,
        area_px=area_px,
        area_mm2=area_px * (x_mm * y_mm),
        longest_extent_mm=rectangle.long_side,
        shortest_extent_mm=rectangle.short_side,
        centroid=centroid,
        bbox_px=(left, top, left + width, top + height),
        rectangle_px=(corners[0], corners[1], corners[2], corners[3]),
        touches_border=(
            left == 0 or top == 0 or left + width == mask.width_px or top + height == mask.height_px
        ),
        zone=zones[0].zone_id if zones else None,
        zones=zones,
    )


def measure_regions(
    mask: CalibratedMask, zone_map: ZoneMap | None = None, *, min_area_px: int = 1
) -> tuple[MeasuredRegion, ...]:
    """Measure every connected region of a mask.

    Each region gets its longest extent (the long side of its minimum-area
    rectangle) and its area in millimetres from the mask's calibration, and
    the strictest zone it touches. Every number comes from the mask's pixels
    and the declared calibration, and from nowhere else.

    Args:
        mask: The mask and its calibration.
        zone_map: The board's zones; without one, no region has a zone.
        min_area_px: Regions of fewer pixels are dropped; the rest keep the
            labels `label_regions` gives them.

    Returns:
        The regions in label order.

    Raises:
        ValueError: If `min_area_px` is below one pixel.
    """
    if min_area_px < 1:
        msg = f"min_area_px must be at least 1, got {min_area_px}"
        raise ValueError(msg)
    zones = zone_map if zone_map is not None else ZoneMap()
    labels, boxes = _label(mask.pixels)
    measured: list[MeasuredRegion] = []
    for label, (left, top, width, height, area) in enumerate(boxes.tolist(), start=1):
        if area >= min_area_px:
            region = labels[top : top + height, left : left + width] == label
            measured.append(
                _measure(region, label=label, origin_px=(left, top), mask=mask, zone_map=zones)
            )
    return tuple(measured)
