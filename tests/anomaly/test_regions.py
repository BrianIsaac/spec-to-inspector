"""Tests for the geometry between an anomaly map and its regions and crops."""

import numpy as np
import pytest

from spec_to_inspector.anomaly.records import Box
from spec_to_inspector.anomaly.regions import crop_box, find_regions, upsample


def _scores(height: int = 40, width: int = 60) -> np.ndarray:
    return np.zeros((height, width), dtype=np.float32)


def test_upsampling_reaches_the_source_size_and_keeps_the_range() -> None:
    """A map is stretched to the source's width and height, never beyond its own values."""
    small = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

    large = upsample(small, width=6, height=4)

    assert large.shape == (4, 6)
    assert large.dtype == np.float32
    assert large.min() == 0.0
    assert large.max() == 3.0
    assert large[0, 0] == 0.0
    assert large[-1, -1] == 3.0


def test_upsampling_to_the_same_size_changes_nothing() -> None:
    """A map already at the source's size is returned as it is."""
    scores = np.arange(12, dtype=np.float32).reshape(3, 4)

    assert np.array_equal(upsample(scores, width=4, height=3), scores)


def test_regions_are_the_connected_areas_above_the_threshold() -> None:
    """Each connected area above the threshold is one region with its box, area and centroid."""
    scores = _scores()
    scores[5:10, 10:30] = 2.0
    scores[20:26, 40:44] = 3.0

    labels, regions = find_regions(scores, threshold=1.0)

    assert len(regions) == 2
    assert labels.dtype == np.uint16
    assert labels.shape == scores.shape
    first, second = regions
    assert (first.index, second.index) == (1, 2)
    assert first.bbox == Box(x=40, y=20, width=4, height=6)
    assert first.area_px == 24
    assert first.centroid == (41.5, 22.5)
    assert second.bbox == Box(x=10, y=5, width=20, height=5)
    assert second.area_px == 100
    assert np.array_equal(labels == 1, scores == 3.0)
    assert np.array_equal(labels == 2, scores == 2.0)


def test_regions_are_ranked_by_their_peak_score() -> None:
    """Region 1 is the one holding the highest score, whatever its size or position."""
    scores = _scores()
    scores[0:20, 0:20] = 2.0
    scores[30:32, 50:52] = 2.5
    scores[31, 51] = 9.0

    _, regions = find_regions(scores, threshold=1.0)

    assert [r.area_px for r in regions] == [4, 400]
    assert regions[0].peak_score == 9.0
    assert regions[0].peak_xy == (51, 31)
    assert regions[0].mean_score == pytest.approx((2.5 * 3 + 9.0) / 4)
    assert regions[1].peak_score == 2.0


def test_equal_peaks_are_ordered_by_area_then_position() -> None:
    """Ties are broken the same way every time: the larger first, then top to bottom."""
    scores = _scores()
    scores[30:32, 0:2] = 2.0
    scores[10:12, 0:2] = 2.0
    scores[0:3, 20:23] = 2.0

    _, regions = find_regions(scores, threshold=1.0)

    assert [(r.bbox.x, r.bbox.y) for r in regions] == [(20, 0), (0, 10), (0, 30)]


def test_diagonal_neighbours_are_one_region() -> None:
    """Regions are 8-connected: pixels touching at a corner belong together."""
    scores = _scores()
    scores[5, 5] = 2.0
    scores[6, 6] = 2.0

    _, regions = find_regions(scores, threshold=1.0)

    assert len(regions) == 1
    assert regions[0].bbox == Box(x=5, y=5, width=2, height=2)
    assert regions[0].area_px == 2


def test_the_threshold_itself_is_not_anomalous() -> None:
    """A pixel must exceed the threshold, as Anomalib's own mask requires."""
    scores = _scores()
    scores[5, 5] = 1.0

    labels, regions = find_regions(scores, threshold=1.0)

    assert regions == []
    assert not labels.any()


def test_small_regions_are_dropped_from_the_labels_too() -> None:
    """A region under the minimum area leaves neither a record nor pixels in the label image."""
    scores = _scores()
    scores[5, 5] = 9.0
    scores[20:24, 20:24] = 2.0

    labels, regions = find_regions(scores, threshold=1.0, min_area=4)

    assert len(regions) == 1
    assert regions[0].area_px == 16
    assert regions[0].index == 1
    assert labels[5, 5] == 0
    assert set(np.unique(labels).tolist()) == {0, 1}


def test_a_crop_box_adds_a_margin_and_reaches_the_minimum_side() -> None:
    """The crop is the region's box plus a margin, grown to the minimum side."""
    box = crop_box(
        Box(x=500, y=400, width=100, height=40), width=1358, height=1104, margin=0.5, min_side=64
    )
    assert box == Box(x=450, y=350, width=200, height=140)

    grown = crop_box(
        Box(x=500, y=400, width=10, height=10), width=1358, height=1104, margin=0.5, min_side=256
    )
    assert (grown.width, grown.height) == (256, 256)
    assert grown.x <= 500
    assert grown.x + grown.width >= 510
    assert (grown.x, grown.y) == (377, 277)


def test_a_crop_box_at_the_edge_is_shifted_inside_not_shrunk() -> None:
    """Near an edge the crop keeps its size and slides into the image."""
    box = crop_box(
        Box(x=0, y=1100, width=4, height=4), width=1358, height=1104, margin=0.5, min_side=256
    )

    assert box == Box(x=0, y=848, width=256, height=256)


def test_a_crop_box_never_exceeds_the_image() -> None:
    """A region as large as the image is cropped to the image."""
    box = crop_box(
        Box(x=0, y=0, width=60, height=40), width=60, height=40, margin=0.5, min_side=256
    )

    assert box == Box(x=0, y=0, width=60, height=40)
