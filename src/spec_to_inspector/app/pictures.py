"""The pictures the console draws itself: thumbnails, heatmaps and specification pages.

Crops and the judge's overlays are served as the files they are. These three
are made on request and kept in memory: a board's thumbnail for the batch
grid, the anomaly map coloured over a crop, and a page of the specification's
PDF beside its clause table.
"""

import io
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Final, cast

import cv2
import numpy as np
import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray
from PIL import Image, UnidentifiedImageError

from spec_to_inspector.anomaly.records import ImageResult, Region
from spec_to_inspector.anomaly.regions import upsample

_JPEG_QUALITY: Final = 88
_FAINTEST: Final = 0.1
_STRONGEST: Final = 0.7
_OUTLINE: Final = (255, 255, 255)

# PDFium is not safe to call from two threads at once, and the pages are
# requested from the server's thread pool.
_PDFIUM: Final = Lock()


class PictureError(LookupError):
    """A picture could not be drawn; the message says why."""


def _stamp(path: Path) -> int:
    """Give a file's modification time, so a cached picture follows its source.

    Args:
        path: The source file.

    Returns:
        The modification time in nanoseconds.

    Raises:
        PictureError: If the file cannot be read.
    """
    try:
        return path.stat().st_mtime_ns
    except OSError as error:
        msg = f"{path} cannot be read: {error}"
        raise PictureError(msg) from error


@lru_cache(maxsize=1024)
def _thumbnail(path: Path, stamp: int, width: int) -> bytes:
    try:
        with Image.open(path) as opened:
            opened.draft("RGB", (width, width))
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as error:
        msg = f"{path} is not a picture this console can read: {error}"
        raise PictureError(msg) from error
    if image.width > width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def thumbnail(path: Path, *, width: int) -> bytes:
    """Draw a photograph smaller, in proportion.

    Args:
        path: The photograph.
        width: The width wanted, in pixels; a narrower photograph is kept as it is.

    Returns:
        The thumbnail as a JPEG.

    Raises:
        PictureError: If the file is missing or is not a picture.
    """
    return _thumbnail(path, _stamp(path), width)


@lru_cache(maxsize=256)
def _heatmap(directory: Path, stamp: int, result: str, index: int) -> bytes:
    sidecar = ImageResult.model_validate_json(result)
    region = next(r for r in sidecar.regions if r.index == index)
    box = region.crop_box
    if region.crop is None or box is None:
        msg = f"region {index} of {sidecar.image_id} has no crop to draw the anomaly map on"
        raise PictureError(msg)
    try:
        with Image.open(directory / region.crop) as opened:
            crop = np.asarray(opened.convert("RGB"))
        stored = cast("NDArray[np.float32]", np.load(directory / sidecar.anomaly_map))
    except (OSError, ValueError, UnidentifiedImageError) as error:
        msg = f"the crop or the anomaly map of {sidecar.image_id} cannot be read: {error}"
        raise PictureError(msg) from error
    stretched = upsample(stored, width=sidecar.width, height=sidecar.height)
    scores = stretched[box.y : box.y + box.height, box.x : box.x + box.width]
    if scores.shape != crop.shape[:2]:
        msg = (
            f"the crop of region {index} of {sidecar.image_id} is {crop.shape[1]} by "
            f"{crop.shape[0]} pixels, not the {box.width} by {box.height} its result records"
        )
        raise PictureError(msg)

    floor = float(stored.min())
    span = max(float(stored.max()), sidecar.region_threshold) - floor
    heat = np.clip((scores - floor) / span, 0.0, 1.0) if span > 0 else np.zeros_like(scores)
    levels = np.round(heat * 255).astype(np.uint8)
    colours = cast(
        "NDArray[np.uint8]",
        cv2.cvtColor(cv2.applyColorMap(levels, cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB),
    )
    weight = (_FAINTEST + (_STRONGEST - _FAINTEST) * heat)[..., np.newaxis]
    drawn = np.round(crop * (1.0 - weight) + colours * weight).astype(np.uint8)
    flagged = (scores > sidecar.region_threshold).astype(np.uint8)
    contours, _ = cv2.findContours(flagged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(drawn, contours, -1, _OUTLINE, 2)

    buffer = io.BytesIO()
    Image.fromarray(drawn).save(buffer, format="PNG")
    return buffer.getvalue()


def heatmap(directory: Path, result: ImageResult, region: Region) -> bytes:
    """Draw the anomaly map over one region's crop.

    The whole rectangle is tinted, from blue where the board is most like a
    good one to red at the map's peak, more strongly the hotter it is; a
    white line runs where the map crosses the threshold the region was cut
    at, which is the outline of what was flagged.

    Args:
        directory: The board's directory in the run.
        result: The anomaly model's result for the board.
        region: The region whose crop is drawn on.

    Returns:
        The heatmap as a PNG of the crop's own size.

    Raises:
        PictureError: If the region has no crop, or the crop or the map
            cannot be read or do not fit each other.
    """
    if region.crop is None or region.crop_box is None:
        msg = f"region {region.index} of {result.image_id} has no crop to draw the anomaly map on"
        raise PictureError(msg)
    return _heatmap(
        directory, _stamp(directory / result.anomaly_map), result.model_dump_json(), region.index
    )


@lru_cache(maxsize=64)
def _pdf_page(path: Path, stamp: int, page: int, width: int) -> bytes:
    with _PDFIUM:
        try:
            # pypdfium2 ships no type stubs; its objects are used through `Any`.
            document: Any = pdfium.PdfDocument(path)
        except (pdfium.PdfiumError, OSError) as error:
            msg = f"{path} cannot be opened as a PDF: {error}"
            raise PictureError(msg) from error
        try:
            pages = len(document)
            if not 1 <= page <= pages:
                counted = "1 page" if pages == 1 else f"{pages} pages"
                msg = f"{path.name} has {counted}; there is no page {page}"
                raise PictureError(msg)
            sheet = document[page - 1]
            drawn = cast("Image.Image", sheet.render(scale=width / sheet.get_width()).to_pil())
            image = drawn.convert("RGB")
        finally:
            document.close()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def pdf_page(path: Path, page: int, *, width: int) -> bytes:
    """Draw one page of a PDF.

    Args:
        path: The PDF.
        page: The page, from 1.
        width: The width wanted, in pixels.

    Returns:
        The page as a PNG.

    Raises:
        PictureError: If the file is not a PDF or has no such page.
    """
    return _pdf_page(path, _stamp(path), page, width)
