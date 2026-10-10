"""Which zones of the board a region touches, by overlap and by centroid."""

import numpy as np
import numpy.typing as npt

from spec_to_inspector.measure.models import BoolArray, Zone, ZoneMap, ZoneOverlap

# Zone edges are rounded to this many decimals of a pixel, so an edge such as
# 0.3 of 100 pixels (30.000000000000004 in floating point) lands on column 30
# and does not claim a sliver of the next pixel.
_EDGE_DECIMALS = 9


def _covered(start: int, count: int, low: float, high: float, size: int) -> npt.NDArray[np.float64]:
    """Give how much of each pixel in a run lies between two normalised edges.

    Args:
        start: The first pixel's index along the axis.
        count: The number of pixels in the run.
        low: The lower edge, normalised.
        high: The upper edge, normalised.
        size: The mask's size along the axis, in pixels.

    Returns:
        For each pixel, the length of it between the edges, from 0 to 1.
    """
    near = np.arange(start, start + count, dtype=np.float64)
    low_px = round(low * size, _EDGE_DECIMALS)
    high_px = round(high * size, _EDGE_DECIMALS)
    return np.clip(np.minimum(near + 1.0, high_px) - np.maximum(near, low_px), 0.0, None)


def _overlap(
    region: BoolArray,
    area_px: int,
    zone: Zone,
    origin_px: tuple[int, int],
    mask_size_px: tuple[int, int],
) -> float:
    """Give the share of a region's area that lies in a zone.

    Args:
        region: The region's pixels within its bounding box.
        area_px: The number of pixels in the region.
        zone: The zone.
        origin_px: The bounding box's top-left pixel (x, y) in the mask.
        mask_size_px: The mask's width and height in pixels.

    Returns:
        The share, from 0 to 1; a pixel cut by the zone's edge counts for the
        part of it inside.
    """
    height, width = region.shape
    across = _covered(origin_px[0], width, zone.x_min, zone.x_max, mask_size_px[0])
    down = _covered(origin_px[1], height, zone.y_min, zone.y_max, mask_size_px[1])
    inside = float(down @ (region.astype(np.float64) @ across))
    return min(inside / area_px, 1.0)


def touched_zones(
    region: BoolArray,
    *,
    origin_px: tuple[int, int],
    mask_size_px: tuple[int, int],
    centroid: tuple[float, float],
    zone_map: ZoneMap,
) -> tuple[ZoneOverlap, ...]:
    """Find every zone a region touches, the strictest first.

    A region touches a zone when any of its area lies in the zone or when its
    centroid does; the centroid matters for a region that curls around a zone
    without covering it. Sharing only an edge with a zone is not touching it.
    The first zone returned is the one whose limits apply: where a region
    straddles zones, the stricter wins.

    Args:
        region: The region's pixels within its bounding box.
        origin_px: The bounding box's top-left pixel (x, y) in the mask.
        mask_size_px: The mask's width and height in pixels.
        centroid: The region's centroid, normalised (x, y).
        zone_map: The board's zones.

    Returns:
        One entry per zone touched, ordered by rank; empty if the region lies
        outside every zone.
    """
    area_px = int(np.count_nonzero(region))
    touched: list[ZoneOverlap] = []
    for zone in zone_map.strictest_first:
        fraction = _overlap(region, area_px, zone, origin_px, mask_size_px)
        holds_centroid = (
            zone.x_min <= centroid[0] <= zone.x_max and zone.y_min <= centroid[1] <= zone.y_max
        )
        if fraction > 0.0 or holds_centroid:
            touched.append(
                ZoneOverlap(
                    zone_id=zone.id,
                    rank=zone.rank,
                    overlap_fraction=fraction,
                    contains_centroid=holds_centroid,
                )
            )
    return tuple(touched)
