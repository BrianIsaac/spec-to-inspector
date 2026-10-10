"""The specification's figures, built from VisA images.

A figure's source is written in the Markdown as the image's title:
`visa:<image path>#zones` draws the part's zones on the whole image, and
`visa:<image path>#mask=<value>` crops the image around the pixels of that
value in its mask (VisA's masks number their defect types). The image path is
the one `image_anno.csv` lists, so the part is its first component. The
figures are small JPEGs kept beside the Markdown, rebuilt from `data/visa` by
one command; VisA is licensed CC BY 4.0 and the specification credits it.
"""

import csv
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from spec_to_inspector.spec.extract import extract_specification
from spec_to_inspector.spec.markdown import FigureSource, figure_sources, read_markdown
from spec_to_inspector.spec.schema import Zone

ZONE_FIGURE_WIDTH: Final = 720
CROP_SIZE: Final = (600, 450)
ZONE_COLOURS: Final = ((255, 107, 0), (255, 230, 0), (255, 255, 255))
JPEG_QUALITY: Final = 85

_SOURCE: Final = re.compile(r"^visa:(?P<image>[^#]+)#(?:(?P<zones>zones)|mask=(?P<mask>\d+))$")
_OUTLINE: Final = 5
_CROP_PADDING: Final = 0.6
_CROP_MIN_WIDTH: Final = 260
_MARKER_MARGIN: Final = 8


class FigureError(ValueError):
    """A figure cannot be built from its source."""


def _mask_path(visa_dir: Path, image: str) -> Path:
    """Find the mask `image_anno.csv` lists for an image.

    Args:
        visa_dir: The dataset directory.
        image: The image's path as the CSV lists it.

    Returns:
        The mask's path.

    Raises:
        FigureError: If the CSV does not list the image with a mask.
    """
    annotations = visa_dir / Path(image).parts[0] / "image_anno.csv"
    with annotations.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["image"] == image and row["mask"]:
                return visa_dir / row["mask"]
    raise FigureError(f"{annotations} lists no mask for {image}")


def _crop_box(
    bounds: tuple[int, int, int, int], size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Give the crop around a defect: padded, in the figure's shape, inside the image.

    Args:
        bounds: The defect's bounding box, left, top, right, bottom.
        size: The image's width and height.

    Returns:
        The crop's box, left, top, right, bottom.
    """
    aspect = CROP_SIZE[0] / CROP_SIZE[1]
    left, top, right, bottom = bounds
    width = max((right - left) * (1 + 2 * _CROP_PADDING), _CROP_MIN_WIDTH)
    height = max((bottom - top) * (1 + 2 * _CROP_PADDING), _CROP_MIN_WIDTH / aspect)
    width, height = max(width, height * aspect), max(height, width / aspect)
    width, height = min(width, size[0]), min(height, size[1])
    x0 = min(max((left + right - width) / 2, 0), size[0] - width)
    y0 = min(max((top + bottom - height) / 2, 0), size[1] - height)
    return round(x0), round(y0), round(x0 + width), round(y0 + height)


def _defect_crop(image: Image.Image, mask: Image.Image, value: int, what: str) -> Image.Image:
    """Crop an image around the mask pixels of one value and mark them.

    Args:
        image: The board's image.
        mask: Its mask, numbered by defect type.
        value: The mask value to show.
        what: The figure's source, for the error.

    Returns:
        The crop, at the figure's size, with the defect's bounds outlined.

    Raises:
        FigureError: If the mask has no pixel of that value.
    """
    bounds = mask.point([255 if level == value else 0 for level in range(256)]).getbbox()
    if bounds is None:
        raise FigureError(f"{what}: the mask has no pixel of value {value}")
    box = _crop_box(bounds, image.size)
    crop = image.crop(box).resize(CROP_SIZE, Image.Resampling.LANCZOS)
    scale = CROP_SIZE[0] / (box[2] - box[0])
    ImageDraw.Draw(crop).rectangle(
        (
            (bounds[0] - box[0]) * scale - _MARKER_MARGIN,
            (bounds[1] - box[1]) * scale - _MARKER_MARGIN,
            (bounds[2] - box[0]) * scale + _MARKER_MARGIN,
            (bounds[3] - box[1]) * scale + _MARKER_MARGIN,
        ),
        outline=ZONE_COLOURS[0],
        width=3,
    )
    return crop


def _zone_drawing(image: Image.Image, zones: Sequence[Zone]) -> Image.Image:
    """Draw a part's zones on its whole image, the most critical drawn last.

    Args:
        image: The board's image.
        zones: The part's zones.

    Returns:
        The image at the figure's width, each zone outlined and lettered.
    """
    height = ZONE_FIGURE_WIDTH * image.height // image.width
    drawn = image.resize((ZONE_FIGURE_WIDTH, height), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(drawn)
    font = ImageFont.load_default(size=44)
    for zone in sorted(zones, key=lambda zone: -zone.rank):
        colour = ZONE_COLOURS[(zone.rank - 1) % len(ZONE_COLOURS)]
        left, top = zone.x0 * ZONE_FIGURE_WIDTH, zone.y0 * height
        draw.rectangle(
            (left, top, zone.x1 * ZONE_FIGURE_WIDTH, zone.y1 * height),
            outline=colour,
            width=_OUTLINE,
        )
        tag = (left + _OUTLINE, top + _OUTLINE, left + _OUTLINE + 46, top + _OUTLINE + 52)
        draw.rectangle(tag, fill=colour)
        draw.text((tag[0] + 8, tag[1] + 1), zone.name, fill=(0, 0, 0), font=font)
    return drawn


def build_figure(
    figure: FigureSource, *, visa_dir: Path, zones: Sequence[Zone], out_dir: Path
) -> Path:
    """Build one figure from its VisA source.

    Args:
        figure: The figure, with its source and its path relative to `out_dir`.
        visa_dir: The dataset directory, as `data fetch` leaves it.
        zones: The zones of the whole specification; the image's part picks its own.
        out_dir: The directory the figure's path is relative to.

    Returns:
        The file written.

    Raises:
        FigureError: If the source is outside the grammar, the image or its
            mask is not in the dataset, or there is nothing to draw.
    """
    what = f"figure {figure.path} ({figure.source!r})"
    if not figure.source.startswith("visa:"):
        raise FigureError(f"figure {figure.path} has no source of the form visa:<image>#...")
    parsed = _SOURCE.fullmatch(figure.source)
    if parsed is None:
        raise FigureError(f"{what}: the source must end with #zones or #mask=<value>")
    path = (visa_dir / parsed["image"]).resolve()
    if not path.is_relative_to(visa_dir.resolve()):
        raise FigureError(f"{what}: the image is outside the dataset directory")
    if not path.is_file():
        raise FigureError(f"{what}: {path} is not in the dataset; run `data fetch`")
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    if parsed["zones"]:
        own = [zone for zone in zones if zone.category == Path(parsed["image"]).parts[0]]
        if not own:
            raise FigureError(f"{what}: the specification gives the part no zones")
        built = _zone_drawing(image, own)
    else:
        with Image.open(_mask_path(visa_dir, parsed["image"])) as mask:
            built = _defect_crop(image, mask.convert("L"), int(parsed["mask"]), what)
    out = out_dir / figure.path
    out.parent.mkdir(parents=True, exist_ok=True)
    built.save(out, quality=JPEG_QUALITY, optimize=True)
    return out


def build_figures(markdown_path: Path, *, visa_dir: Path) -> list[Path]:
    """Build every figure a specification's Markdown source names.

    Args:
        markdown_path: The Markdown source; figures are written relative to it.
        visa_dir: The dataset directory, as `data fetch` leaves it.

    Returns:
        The files written, in the order the source shows them.

    Raises:
        FigureError: If a figure cannot be built.
        SpecificationError: If the source is not a valid specification.
    """
    text = markdown_path.read_text(encoding="utf-8")
    zones = extract_specification(read_markdown(text), pages=1).zones
    return [
        build_figure(figure, visa_dir=visa_dir, zones=zones, out_dir=markdown_path.parent)
        for figure in figure_sources(text)
    ]
