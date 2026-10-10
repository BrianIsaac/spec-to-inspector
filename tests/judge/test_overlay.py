"""Tests for the heatmap overlay the judge is shown beside the crop."""

import io

import numpy as np
import pytest
from PIL import Image

from spec_to_inspector.judge.overlay import encode_png, heatmap_overlay


def _scene() -> tuple[
    np.ndarray[tuple[int, int, int], np.dtype[np.uint8]],
    np.ndarray[tuple[int, int], np.dtype[np.float32]],
    np.ndarray[tuple[int, int], np.dtype[np.bool_]],
]:
    crop = np.full((60, 80, 3), 120, dtype=np.uint8)
    scores = np.full((60, 80), 10.0, dtype=np.float32)
    scores[20:40, 30:60] = 35.0
    scores[28:32, 40:50] = 50.0
    region = scores > 30.0
    return crop, scores, region


def test_the_overlay_is_the_crops_size_and_type() -> None:
    """The judge gets two pictures of the same rectangle."""
    crop, scores, region = _scene()

    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=50.0)

    assert overlay.shape == crop.shape
    assert overlay.dtype == np.uint8


def test_what_lies_under_the_threshold_and_off_the_outline_is_the_board_itself() -> None:
    """Only the anomalous area is tinted, so the board around it stays readable."""
    crop, scores, region = _scene()

    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=50.0)

    assert np.array_equal(overlay[:10], crop[:10])
    assert np.array_equal(overlay[50:], crop[50:])
    assert np.array_equal(overlay[:, :20], crop[:, :20])


def test_the_hotter_the_score_the_redder_and_the_stronger_the_tint() -> None:
    """The peak reads red and the edge of the region reads cooler."""
    crop, scores, region = _scene()

    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=50.0).astype(int)

    peak = overlay[30, 45]
    warm = overlay[24, 35]
    assert peak[0] > peak[2]
    assert peak[0] > warm[0]
    assert abs(peak - 120).sum() > abs(warm - 120).sum() > 0


def test_the_regions_outline_is_drawn() -> None:
    """A light line marks the region's edge, whatever the board's colour there."""
    crop, scores, region = _scene()

    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=50.0)

    assert (overlay[20, 30:60] == 255).all()
    assert (overlay[39, 30:60] == 255).all()
    assert (overlay[20:40, 30] == 255).all()


def test_a_peak_patch_under_the_threshold_is_still_marked() -> None:
    """A region the map never lifts above the threshold is still outlined and tinted."""
    crop = np.full((60, 80, 3), 120, dtype=np.uint8)
    scores = np.full((60, 80), 10.0, dtype=np.float32)
    scores[20:40, 30:60] = 22.0
    region = np.zeros((60, 80), dtype=np.bool_)
    region[20:40, 30:60] = True

    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=24.0)

    assert not np.array_equal(overlay[30, 45], crop[30, 45])
    assert (overlay[20, 30:60] == 255).all()
    assert np.array_equal(overlay[:10], crop[:10])


def test_a_flat_map_does_not_divide_by_zero() -> None:
    """A region whose scores are all one value is tinted evenly."""
    crop = np.full((20, 20, 3), 90, dtype=np.uint8)
    scores = np.full((20, 20), 40.0, dtype=np.float32)
    region = np.zeros((20, 20), dtype=np.bool_)
    region[5:15, 5:15] = True

    overlay = heatmap_overlay(crop, scores, region, low=40.0, high=40.0)

    assert np.isfinite(overlay).all()
    assert not np.array_equal(overlay[10, 10], crop[10, 10])


@pytest.mark.parametrize(
    ("scores_shape", "region_shape"), [((60, 81), (60, 80)), ((60, 80), (61, 80))]
)
def test_arrays_of_different_sizes_are_refused(
    scores_shape: tuple[int, int], region_shape: tuple[int, int]
) -> None:
    """The crop, its scores and its region are one rectangle."""
    crop = np.zeros((60, 80, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="same rectangle"):
        heatmap_overlay(
            crop,
            np.zeros(scores_shape, dtype=np.float32),
            np.zeros(region_shape, dtype=np.bool_),
            low=1.0,
            high=2.0,
        )


def test_png_bytes_decode_to_the_same_pixels() -> None:
    """The encoding is lossless."""
    crop, scores, region = _scene()
    overlay = heatmap_overlay(crop, scores, region, low=30.0, high=50.0)

    decoded = np.asarray(Image.open(io.BytesIO(encode_png(overlay))).convert("RGB"))

    assert np.array_equal(decoded, overlay)
