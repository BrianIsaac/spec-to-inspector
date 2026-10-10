"""Tests for the measurement inputs: the calibration, the mask and the zones."""

import numpy as np
import pytest
from pydantic import ValidationError

from spec_to_inspector.measure.models import CalibratedMask, Calibration, Zone, ZoneMap


def _calibration(
    board_width_mm: float = 64.0, width_px: int = 256, height_px: int = 128
) -> Calibration:
    return Calibration(
        board_width_mm=board_width_mm, image_width_px=width_px, image_height_px=height_px
    )


def _zone(
    zone_id: str = "A", rank: int = 1, box: tuple[float, float, float, float] = (0, 0, 1, 1)
) -> Zone:
    return Zone(id=zone_id, rank=rank, x_min=box[0], y_min=box[1], x_max=box[2], y_max=box[3])


def test_the_scale_is_the_board_width_over_the_image_width() -> None:
    """A 64 mm board across 256 pixels is a quarter of a millimetre per pixel."""
    assert _calibration().mm_per_px == 0.25


def test_a_mask_at_the_image_size_has_square_pixels_at_exactly_the_scale() -> None:
    """No rounding creeps in when the mask is the image: both sides equal the declared scale."""
    calibration = _calibration(board_width_mm=100.0, width_px=1562, height_px=1024)

    size = calibration.pixel_size_mm(mask_width_px=1562, mask_height_px=1024)

    assert size == (100.0 / 1562, 100.0 / 1562)


def test_a_squashed_mask_has_pixels_that_are_not_square() -> None:
    """A 1562 by 1024 image squashed to 256 by 256 has mask pixels wider than they are tall."""
    calibration = _calibration(board_width_mm=100.0, width_px=1562, height_px=1024)

    x_mm, y_mm = calibration.pixel_size_mm(mask_width_px=256, mask_height_px=256)

    assert x_mm == pytest.approx(100.0 / 256)
    assert y_mm == pytest.approx((100.0 / 1562) * 1024 / 256)
    assert x_mm * 256 == pytest.approx(100.0)
    assert y_mm * 256 == pytest.approx(100.0 * 1024 / 1562)


@pytest.mark.parametrize("width_mm", [0.0, -1.0, float("nan"), float("inf")])
def test_a_board_width_that_is_not_a_positive_length_is_refused(width_mm: float) -> None:
    """A scale of zero, a negative scale or no scale at all would make every size meaningless."""
    with pytest.raises(ValidationError):
        _calibration(board_width_mm=width_mm)


@pytest.mark.parametrize(("width_px", "height_px"), [(0, 10), (10, 0), (-5, 10)])
def test_an_image_without_pixels_is_refused(width_px: int, height_px: int) -> None:
    """The image size divides the board width, so it must be positive."""
    with pytest.raises(ValidationError):
        _calibration(width_px=width_px, height_px=height_px)


def test_a_mask_knows_its_size_and_its_pixel_size() -> None:
    """Width is the number of columns, height the number of rows."""
    mask = CalibratedMask(pixels=np.zeros((128, 256), dtype=np.bool_), calibration=_calibration())

    assert (mask.width_px, mask.height_px) == (256, 128)
    assert mask.pixel_size_mm == (0.25, 0.25)


def test_a_mask_cannot_be_written_through_the_model() -> None:
    """The model is frozen, and so is the array it holds."""
    mask = CalibratedMask(pixels=np.zeros((4, 4), dtype=np.bool_), calibration=_calibration())

    with pytest.raises(ValueError, match="read-only"):
        mask.pixels[0, 0] = True


def test_the_caller_keeps_a_writable_array() -> None:
    """Freezing the model's view leaves the caller's own array as it was."""
    pixels = np.zeros((4, 4), dtype=np.bool_)

    CalibratedMask(pixels=pixels, calibration=_calibration())
    pixels[0, 0] = True

    assert pixels[0, 0]


@pytest.mark.parametrize(
    "pixels",
    [
        np.zeros((4, 4), dtype=np.uint8),
        np.zeros((4, 4), dtype=np.float32),
        np.zeros((4, 4, 3), dtype=np.bool_),
        np.zeros((4,), dtype=np.bool_),
        np.zeros((0, 4), dtype=np.bool_),
        [[True, False], [False, True]],
    ],
    ids=["uint8", "float32", "three-dimensional", "one-dimensional", "empty", "a list"],
)
def test_only_a_two_dimensional_boolean_array_is_a_mask(pixels: object) -> None:
    """An anomaly map or a 0 and 255 image passed by mistake is refused, not thresholded here."""
    with pytest.raises(ValidationError):
        CalibratedMask(pixels=pixels, calibration=_calibration())  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "box",
    [
        (0.5, 0.0, 0.5, 1.0),
        (0.6, 0.0, 0.5, 1.0),
        (0.0, 0.5, 1.0, 0.5),
        (0.0, 0.6, 1.0, 0.5),
        (-0.1, 0.0, 1.0, 1.0),
        (0.0, 0.0, 1.1, 1.0),
        (0.0, 0.0, 1.0, float("nan")),
    ],
)
def test_a_zone_is_a_rectangle_with_area_inside_the_image(
    box: tuple[float, float, float, float],
) -> None:
    """Normalised coordinates run from 0 to 1 and the rectangle has a positive size."""
    with pytest.raises(ValidationError):
        _zone(box=box)


@pytest.mark.parametrize(("zone_id", "rank"), [("", 1), ("A", 0), ("A", -1)])
def test_a_zone_needs_a_name_and_a_rank_from_one(zone_id: str, rank: int) -> None:
    """Rank 1 is the strictest zone; there is no rank below it."""
    with pytest.raises(ValidationError):
        _zone(zone_id=zone_id, rank=rank)


def test_a_zone_map_lists_its_zones_strictest_first() -> None:
    """Whatever order the zones are declared in, the map reads them by rank."""
    zone_map = ZoneMap(zones=(_zone("C", 3), _zone("A", 1), _zone("B", 2)))

    assert [zone.id for zone in zone_map.strictest_first] == ["A", "B", "C"]


def test_a_zone_map_may_be_empty() -> None:
    """A specification without zones is a map with none; every region then has no zone."""
    assert ZoneMap(zones=()).strictest_first == ()


def test_two_zones_cannot_share_a_name() -> None:
    """A clause names its zone by id, so the id must pick one rectangle."""
    with pytest.raises(ValidationError, match="more than once"):
        ZoneMap(zones=(_zone("A", 1), _zone("A", 2)))


def test_two_zones_cannot_share_a_rank() -> None:
    """With equal ranks neither zone is the stricter, so a straddling region has no answer."""
    with pytest.raises(ValidationError, match="rank"):
        ZoneMap(zones=(_zone("A", 1), _zone("B", 1)))
