"""Tests for the anomaly model's records."""

import pytest
import torch
from anomalib.post_processing import PostProcessor
from pydantic import ValidationError

from spec_to_inspector.anomaly.records import Box, Region, Thresholds, normalise


def _thresholds() -> Thresholds:
    return Thresholds(
        image=30.0,
        pixel=25.0,
        image_min=10.0,
        image_max=60.0,
        pixel_min=2.0,
        pixel_max=52.0,
        method="anomalib.metrics.F1AdaptiveThreshold",
        val_split_mode="same_as_test",
        split_images=201,
        split_images_in_test=201,
        tuned_on_test=True,
    )


@pytest.mark.parametrize("value", [-5.0, 10.0, 29.9, 30.0, 30.1, 47.5, 60.0, 400.0])
def test_normalisation_is_anomalibs(value: float) -> None:
    """A raw score is normalised to the value Anomalib's post-processor gives it."""
    expected = PostProcessor._normalize(  # pyright: ignore[reportPrivateUsage]
        torch.tensor(value, dtype=torch.float64),
        torch.tensor(10.0, dtype=torch.float64),
        torch.tensor(60.0, dtype=torch.float64),
        torch.tensor(30.0, dtype=torch.float64),
    )

    assert expected is not None
    assert normalise(value, threshold=30.0, low=10.0, high=60.0) == pytest.approx(expected.item())


def test_the_threshold_normalises_to_a_half() -> None:
    """The image and pixel thresholds each land on 0.5, and the scale is clamped."""
    thresholds = _thresholds()

    assert thresholds.normalise_image(30.0) == 0.5
    assert thresholds.normalise_pixel(25.0) == 0.5
    assert thresholds.normalise_image(55.0) == 1.0
    assert thresholds.normalise_image(1000.0) == 1.0
    assert thresholds.normalise_pixel(-3.0) == 0.0


def test_a_flat_range_still_separates_the_two_sides() -> None:
    """With no range to scale by, a score is 0, 0.5 or 1 by its side of the threshold."""
    assert normalise(2.0, threshold=1.0, low=1.0, high=1.0) == 1.0
    assert normalise(1.0, threshold=1.0, low=1.0, high=1.0) == 0.5
    assert normalise(0.0, threshold=1.0, low=1.0, high=1.0) == 0.0


def test_records_are_frozen_and_round_trip_through_json() -> None:
    """A record cannot be changed after it is made, and JSON gives the same record back."""
    region = Region(
        index=1,
        bbox=Box(x=3, y=4, width=5, height=6),
        area_px=20,
        centroid=(5.5, 6.5),
        peak_score=41.25,
        peak_xy=(5, 6),
        mean_score=33.0,
        crop="crops/region-001.png",
        crop_box=Box(x=0, y=0, width=64, height=64),
    )

    assert Region.model_validate_json(region.model_dump_json()) == region
    with pytest.raises(ValidationError):
        region.index = 2  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "fields", [{"x": -1}, {"y": -1}, {"width": 0}, {"height": 0}], ids=lambda f: next(iter(f))
)
def test_a_box_must_lie_in_the_image_and_cover_a_pixel(fields: dict[str, int]) -> None:
    """A box with a negative corner or no extent is refused."""
    with pytest.raises(ValidationError):
        Box.model_validate({"x": 1, "y": 1, "width": 2, "height": 2} | fields)
