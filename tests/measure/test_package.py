"""Tests for what the measure package offers by name."""

import numpy as np

from spec_to_inspector import measure


def test_the_package_measures_a_mask_end_to_end_from_its_own_names() -> None:
    """A caller needs one import: the inputs, the function and the result are all there."""
    pixels = np.zeros((128, 256), dtype=np.bool_)
    pixels[40:46, 100:130] = True
    mask = measure.CalibratedMask(
        pixels=pixels,
        calibration=measure.Calibration(
            board_width_mm=64.0, image_width_px=256, image_height_px=128
        ),
    )
    zones = measure.ZoneMap(
        zones=(measure.Zone(id="A", rank=1, x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0),)
    )

    (region,) = measure.measure_regions(mask, zones)

    assert isinstance(region, measure.MeasuredRegion)
    assert (region.longest_extent_mm, region.zone) == (7.5, "A")
    assert region.zones == (
        measure.ZoneOverlap(zone_id="A", rank=1, overlap_fraction=1.0, contains_centroid=True),
    )
    assert measure.label_regions(pixels)[1] == 1


def test_the_package_names_exactly_its_public_surface() -> None:
    """Nothing internal leaks into the names other units build on."""
    assert sorted(measure.__all__) == [
        "CalibratedMask",
        "Calibration",
        "MeasuredRegion",
        "Zone",
        "ZoneMap",
        "ZoneOverlap",
        "label_regions",
        "measure_regions",
    ]
