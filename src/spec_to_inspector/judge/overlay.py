"""The heatmap overlay: the crop with the anomaly model's map drawn on it.

The judge is shown two pictures of one rectangle of the board: the crop as
photographed, and this overlay, which says where the anomaly model looked.
Only the region itself is tinted, from blue at its floor to red at its peak,
and its edge is outlined, so the board around it reads as it does in the crop.
"""

import io
from typing import Final, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

_FAINTEST: Final = 0.35
_STRONGEST: Final = 0.75
_OUTLINE: Final = 255


def heatmap_overlay(
    crop: NDArray[np.uint8],
    scores: NDArray[np.float32],
    region: NDArray[np.bool_],
    *,
    low: float,
    high: float,
) -> NDArray[np.uint8]:
    """Draw one region's anomaly scores over its crop.

    A pixel of the region is tinted by where its score lies between the floor
    and `high`; the floor is `low`, or the region's own lowest score if that
    is lower, so a region the map never lifts above the threshold (a peak
    patch) is still tinted. Pixels outside the region keep the crop's colour.

    Args:
        crop: The crop, as (rows, columns, 3) in RGB.
        scores: The raw anomaly map over the same rectangle, as (rows, columns).
        region: True on the region's pixels, over the same rectangle.
        low: The score at which the tint starts: the threshold the region was cut at.
        high: The score drawn as the hottest: the map's peak.

    Returns:
        The overlay, as (rows, columns, 3) in RGB.

    Raises:
        ValueError: If the three arrays do not cover the same rectangle.
    """
    if crop.shape[:2] != scores.shape or scores.shape != region.shape:
        msg = (
            "the crop, its scores and its region must cover the same rectangle, got "
            f"{crop.shape[:2]}, {scores.shape} and {region.shape}"
        )
        raise ValueError(msg)
    overlay = crop.copy()
    if not region.any():
        return overlay

    inside = scores[region]
    floor = min(low, float(inside.min()))
    span = max(high, float(inside.max())) - floor
    heat = np.clip((scores - floor) / span, 0.0, 1.0) if span > 0 else np.ones_like(scores)
    levels = np.round(heat * 255).astype(np.uint8)
    colours = cast(
        "NDArray[np.uint8]",
        cv2.cvtColor(cv2.applyColorMap(levels, cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB),
    )
    weight = (_FAINTEST + (_STRONGEST - _FAINTEST) * heat)[..., np.newaxis]
    blended = crop * (1.0 - weight) + colours * weight
    overlay[region] = np.round(blended[region]).astype(np.uint8)

    contours, _ = cv2.findContours(
        region.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    cv2.drawContours(overlay, contours, -1, (_OUTLINE, _OUTLINE, _OUTLINE), 1)
    return overlay


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """Encode an RGB image as PNG.

    Args:
        image: The image, as (rows, columns, 3) in RGB.

    Returns:
        The PNG file's bytes.
    """
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()
