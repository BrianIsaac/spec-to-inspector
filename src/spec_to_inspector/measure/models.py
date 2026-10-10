"""What measurement takes in and gives back: calibration, mask, zones, measured regions."""

from typing import Annotated, Self

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BoolArray = npt.NDArray[np.bool_]

_Unit = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
_Length = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
_Point = tuple[float, float]


class Calibration(BaseModel):
    """How pixels become millimetres: a declared width over the image's width.

    The specification declares the width in millimetres that the full width of
    the source image spans, which it calls the board width. Source pixels are
    square, so the same scale holds down the image.

    Attributes:
        board_width_mm: The millimetres the full image width spans.
        image_width_px: The source image's width in pixels.
        image_height_px: The source image's height in pixels.
    """

    model_config = ConfigDict(frozen=True)

    board_width_mm: float = Field(gt=0.0, allow_inf_nan=False)
    image_width_px: int = Field(gt=0)
    image_height_px: int = Field(gt=0)

    @property
    def mm_per_px(self) -> float:
        """The side of one source pixel in millimetres."""
        return self.board_width_mm / self.image_width_px

    def pixel_size_mm(self, *, mask_width_px: int, mask_height_px: int) -> tuple[float, float]:
        """Give the size of one pixel of a mask that covers the whole source image.

        A mask at the image's own size has square pixels of exactly `mm_per_px`.
        A mask resized without keeping the aspect ratio (a 1562 by 1024 image
        squashed to 256 by 256) has pixels wider than they are tall, and both
        sides are needed to measure anything that is not axis-aligned.

        Args:
            mask_width_px: The mask's width in pixels.
            mask_height_px: The mask's height in pixels.

        Returns:
            The width and the height of one mask pixel in millimetres.
        """
        return (
            self.mm_per_px * (self.image_width_px / mask_width_px),
            self.mm_per_px * (self.image_height_px / mask_height_px),
        )


class CalibratedMask(BaseModel):
    """A defect mask over the whole source image, with the scale to measure it.

    Attributes:
        pixels: True where the anomaly model marks a defect; rows by columns,
            any resolution, covering the same field of view as the source image.
        calibration: The scale of the source image.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    pixels: BoolArray
    calibration: Calibration

    @field_validator("pixels", mode="after")
    @classmethod
    def _two_dimensional_boolean(cls, value: BoolArray) -> BoolArray:
        """Refuse anything that is not a mask, and hold a view that cannot be written.

        Thresholding is the anomaly model's decision, so an anomaly map or a
        0 and 255 image is refused here instead of being coerced.

        Args:
            value: The array given.

        Returns:
            A read-only view of the array.

        Raises:
            ValueError: If the array is not boolean, not two-dimensional, or empty.
        """
        if value.dtype != np.bool_:
            msg = f"a mask is a boolean array, got dtype {value.dtype}"
            raise ValueError(msg)
        if value.ndim != 2 or value.size == 0:
            msg = f"a mask has rows and columns, got shape {value.shape}"
            raise ValueError(msg)
        view = value.view()
        view.flags.writeable = False
        return view

    @property
    def width_px(self) -> int:
        """The mask's width in pixels."""
        return int(self.pixels.shape[1])

    @property
    def height_px(self) -> int:
        """The mask's height in pixels."""
        return int(self.pixels.shape[0])

    @property
    def pixel_size_mm(self) -> tuple[float, float]:
        """The width and the height of one mask pixel in millimetres."""
        return self.calibration.pixel_size_mm(
            mask_width_px=self.width_px, mask_height_px=self.height_px
        )


class Zone(BaseModel):
    """A named rectangle of the board, in normalised image coordinates.

    The origin is the image's top-left corner, x runs right and y runs down,
    and both run from 0 to 1 whatever the image's resolution.

    Attributes:
        id: The name clauses use for the zone, such as "A".
        rank: How strict the zone is; 1 is the strictest.
        x_min: The left edge.
        y_min: The top edge.
        x_max: The right edge.
        y_max: The bottom edge.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    x_min: _Unit
    y_min: _Unit
    x_max: _Unit
    y_max: _Unit

    @model_validator(mode="after")
    def _has_area(self) -> Self:
        """Refuse a rectangle whose edges cross or touch.

        Returns:
            The zone unchanged.

        Raises:
            ValueError: If the rectangle has no width or no height.
        """
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            msg = f"zone {self.id!r} has no area: its minimum edges must lie below its maximum"
            raise ValueError(msg)
        return self


class ZoneMap(BaseModel):
    """The zones of one board.

    Zones may overlap one another and need not cover the board: where several
    apply the strictest wins, and a region in none of them has no zone.

    Attributes:
        zones: The zones, in any order.
    """

    model_config = ConfigDict(frozen=True)

    zones: tuple[Zone, ...] = ()

    @model_validator(mode="after")
    def _ids_and_ranks_are_unique(self) -> Self:
        """Refuse a map in which a name or a rank picks more than one zone.

        Returns:
            The map unchanged.

        Raises:
            ValueError: If two zones share an id or a rank.
        """
        ids = [zone.id for zone in self.zones]
        ranks = [zone.rank for zone in self.zones]
        repeated_ids = sorted({zone_id for zone_id in ids if ids.count(zone_id) > 1})
        repeated_ranks = sorted({rank for rank in ranks if ranks.count(rank) > 1})
        if repeated_ids:
            msg = f"zone ids declared more than once: {repeated_ids}"
            raise ValueError(msg)
        if repeated_ranks:
            msg = f"zones share a rank, so neither is the stricter: {repeated_ranks}"
            raise ValueError(msg)
        return self

    @property
    def strictest_first(self) -> tuple[Zone, ...]:
        """The zones ordered by rank, the strictest first."""
        return tuple(sorted(self.zones, key=lambda zone: zone.rank))


class ZoneOverlap(BaseModel):
    """How one region relates to one zone it touches.

    Attributes:
        zone_id: The zone's name.
        rank: The zone's rank; 1 is the strictest.
        overlap_fraction: The share of the region's area that lies in the zone.
        contains_centroid: Whether the region's centroid lies in the zone.
    """

    model_config = ConfigDict(frozen=True)

    zone_id: str
    rank: int
    overlap_fraction: _Unit
    contains_centroid: bool


class MeasuredRegion(BaseModel):
    """One connected region of a mask, measured.

    Pixel coordinates are the mask's: x across from the left edge, y down from
    the top edge, a pixel in column c and row r covering the unit square from
    (c, r) to (c + 1, r + 1).

    Attributes:
        label: The region's number in the label image, from 1.
        area_px: The number of mask pixels in the region.
        area_mm2: The region's area in square millimetres.
        longest_extent_mm: The long side of the region's minimum-area rectangle.
        shortest_extent_mm: The short side of the same rectangle.
        centroid: The mean position of the region's pixels, normalised (x, y).
        bbox_px: The axis-aligned box (x_min, y_min, x_max, y_max), maxima exclusive.
        rectangle_px: The minimum-area rectangle's four corners (x, y), in order
            around the rectangle; the rectangle is minimal in millimetres, so
            on a mask with pixels that are not square it may look slanted.
        touches_border: Whether the region reaches the edge of the image, in
            which case its true extent may be larger than the one measured.
        zone: The strictest zone the region touches, or None if it touches none.
        zones: Every zone the region touches, the strictest first.
    """

    model_config = ConfigDict(frozen=True)

    label: int = Field(ge=1)
    area_px: int = Field(ge=1)
    area_mm2: _Length
    longest_extent_mm: _Length
    shortest_extent_mm: _Length
    centroid: tuple[_Unit, _Unit]
    bbox_px: tuple[int, int, int, int]
    rectangle_px: tuple[_Point, _Point, _Point, _Point]
    touches_border: bool
    zone: str | None = None
    zones: tuple[ZoneOverlap, ...] = ()
