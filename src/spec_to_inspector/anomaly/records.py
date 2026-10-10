"""The anomaly model's records: what training and inference write beside their files.

Every model here is frozen and is written as JSON; the files they name are
described where they are written (`spec_to_inspector.anomaly.infer`).
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Final = 1


class Box(BaseModel):
    """An axis-aligned rectangle in a source image's pixels.

    Attributes:
        x: The left column.
        y: The top row.
        width: Columns covered.
        height: Rows covered.
    """

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class Region(BaseModel):
    """One connected area of the thresholded anomaly map, in the source image's pixels.

    Attributes:
        index: The region's rank by peak score, from 1; also the value of its
            pixels in the label image.
        bbox: The tight bounding box.
        area_px: Pixels in the region.
        centroid: The mean position of its pixels, as (x, y).
        peak_score: The highest raw anomaly-map value inside the region.
        peak_xy: Where that value is, as (x, y).
        mean_score: The mean raw anomaly-map value inside the region.
        crop: The crop's file, relative to the sidecar; None if no crop was written.
        crop_box: The rectangle of the source image the crop holds; None with `crop`.
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    bbox: Box
    area_px: int = Field(ge=1)
    centroid: tuple[float, float]
    peak_score: float
    peak_xy: tuple[int, int]
    mean_score: float
    crop: str | None = None
    crop_box: Box | None = None
