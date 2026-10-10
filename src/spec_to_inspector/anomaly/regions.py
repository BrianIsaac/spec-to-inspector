"""From an anomaly map to regions and crop rectangles, in the source image's pixels.

The model scores a 256 x 256 resize of the image; everything downstream
(measurement in millimetres, the crop the judge sees) works in the source
image's own pixels, where a pixel is square. So the map is stretched back to
the source size first, and thresholded there.
"""

import math
from typing import Final, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from spec_to_inspector.anomaly.records import Box, Region

MAX_REGIONS: Final = 65535
"""The most regions a 16-bit label image can number."""


def upsample(anomaly_map: NDArray[np.float32], *, width: int, height: int) -> NDArray[np.float32]:
    """Stretch an anomaly map to the source image's size, bilinearly.

    The same call maps a model-resolution array to source pixels wherever it
    is needed, so a mask recomputed from the stored map equals the stored mask.

    Args:
        anomaly_map: The map, as (rows, columns).
        width: The source image's width in pixels.
        height: The source image's height in pixels.

    Returns:
        The map as (height, width).
    """
    if anomaly_map.shape == (height, width):
        return anomaly_map
    resized = cv2.resize(anomaly_map, (width, height), interpolation=cv2.INTER_LINEAR)
    return cast("NDArray[np.float32]", resized)


def find_regions(
    scores: NDArray[np.float32], *, threshold: float, min_area: int = 1
) -> tuple[NDArray[np.uint16], list[Region]]:
    """Find the connected areas whose score exceeds a threshold.

    Areas are 8-connected. They are ranked by peak score, highest first, with
    ties broken by area (larger first) and then by position (top, then left),
    and numbered from 1 in that order.

    Args:
        scores: Anomaly scores at the source image's size, as (rows, columns).
        threshold: A pixel is anomalous when its score is above this.
        min_area: Areas of fewer pixels are dropped.

    Returns:
        The label image (0 for background, a region's index for its pixels) and
        the regions in rank order, without crops.

    Raises:
        ValueError: If more regions are found than a 16-bit label image can number.
    """
    mask = (scores > threshold).astype(np.uint8)
    count, components, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    raw_labels = cast("NDArray[np.int32]", components)

    found: list[tuple[int, Region]] = []
    for label in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[label])
        if area < min_area:
            continue
        window = scores[y : y + height, x : x + width]
        inside = raw_labels[y : y + height, x : x + width] == label
        values = np.where(inside, window, -np.inf)
        peak_row, peak_column = np.unravel_index(int(np.argmax(values)), values.shape)
        found.append(
            (
                label,
                Region(
                    index=1,
                    bbox=Box(x=x, y=y, width=width, height=height),
                    area_px=area,
                    centroid=(float(centroids[label][0]), float(centroids[label][1])),
                    peak_score=float(window[peak_row, peak_column]),
                    peak_xy=(x + int(peak_column), y + int(peak_row)),
                    mean_score=float(window[inside].mean(dtype=np.float64)),
                ),
            )
        )
    if len(found) > MAX_REGIONS:
        msg = f"{len(found)} regions exceed the {MAX_REGIONS} a label image can number"
        raise ValueError(msg)

    found.sort(
        key=lambda item: (-item[1].peak_score, -item[1].area_px, item[1].bbox.y, item[1].bbox.x)
    )
    renumber = np.zeros(count, dtype=np.uint16)
    regions: list[Region] = []
    for index, (label, region) in enumerate(found, start=1):
        renumber[label] = index
        regions.append(region.model_copy(update={"index": index}))
    return renumber[raw_labels], regions


def crop_box(bbox: Box, *, width: int, height: int, margin: float, min_side: int) -> Box:
    """Choose the rectangle of the source image to cut out around a region.

    The region's box gains a margin on every side, is grown to a minimum side
    so a small defect keeps its surroundings, and is slid inside the image
    rather than shrunk where it meets an edge.

    Args:
        bbox: The region's tight bounding box.
        width: The source image's width in pixels.
        height: The source image's height in pixels.
        margin: The margin on each side, as a fraction of the box's longer side.
        min_side: The least width and height of the crop, where the image allows.

    Returns:
        The crop's rectangle, inside the image.
    """
    pad = math.ceil(margin * max(bbox.width, bbox.height))
    crop_width = min(max(bbox.width + 2 * pad, min_side), width)
    crop_height = min(max(bbox.height + 2 * pad, min_side), height)
    x = (2 * bbox.x + bbox.width - crop_width) // 2
    y = (2 * bbox.y + bbox.height - crop_height) // 2
    return Box(
        x=min(max(x, 0), width - crop_width),
        y=min(max(y, 0), height - crop_height),
        width=crop_width,
        height=crop_height,
    )
