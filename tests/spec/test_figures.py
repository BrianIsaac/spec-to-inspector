"""Tests for the figures built from VisA images."""

from pathlib import Path

import pytest
from PIL import Image

from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.figures import (
    CROP_SIZE,
    ZONE_COLOURS,
    ZONE_FIGURE_WIDTH,
    FigureError,
    build_figure,
    build_figures,
)
from spec_to_inspector.spec.markdown import FigureSource
from tests.spec.spec_fakes import zone

IMAGE = "pcb9/Data/Images/Anomaly/000.JPG"
MASK = "pcb9/Data/Masks/Anomaly/000.png"


@pytest.fixture
def visa(tmp_path: Path) -> Path:
    """Write a one-image VisA tree: a grey 400 by 300 board with a red defect and its mask.

    Returns:
        The dataset directory.
    """
    root = tmp_path / "visa"
    (root / IMAGE).parent.mkdir(parents=True)
    (root / MASK).parent.mkdir(parents=True)
    image = Image.new("RGB", (400, 300), (90, 90, 90))
    image.paste((250, 0, 0), (190, 145, 210, 155))
    image.save(root / IMAGE, quality=95)
    mask = Image.new("L", (400, 300), 0)
    mask.paste(1, (10, 10, 20, 20))
    mask.paste(2, (190, 145, 210, 155))
    mask.save(root / MASK)
    (root / "pcb9" / "image_anno.csv").write_text(
        f'image,label,mask\n{IMAGE},"dirt,scratch",{MASK}\n', encoding="utf-8"
    )
    return root


def figure(source: str, path: str = "figures/out.jpg") -> FigureSource:
    """Build a figure source.

    Returns:
        A figure with a fixed caption.
    """
    return FigureSource(path=path, caption="A figure.", source=source)


def test_a_defect_figure_is_a_crop_centred_on_the_masked_class(visa: Path, tmp_path: Path) -> None:
    """The crop has the fixed size and the defect of the asked mask value at its centre."""
    out = build_figure(
        figure(f"visa:{IMAGE}#mask=2"), visa_dir=visa, zones=(), out_dir=tmp_path / "spec"
    )

    assert out == tmp_path / "spec" / "figures" / "out.jpg"
    with Image.open(out) as crop:
        assert crop.size == CROP_SIZE
        centre = crop.convert("RGB").getpixel((CROP_SIZE[0] // 2, CROP_SIZE[1] // 2))
    assert _near(centre, (250, 0, 0))


def test_a_zone_figure_is_the_whole_image_with_each_zone_outlined(
    visa: Path, tmp_path: Path
) -> None:
    """The figure keeps the image's shape and draws each zone's edge in its rank's colour."""
    zones = (zone("A", 1), zone("B", 2, x0=0.05, y0=0.05, x1=0.95, y1=0.95))

    out = build_figure(figure(f"visa:{IMAGE}#zones"), visa_dir=visa, zones=zones, out_dir=tmp_path)

    with Image.open(out) as drawn:
        assert drawn.size == (ZONE_FIGURE_WIDTH, ZONE_FIGURE_WIDTH * 300 // 400)
        width, height = drawn.size
        on_a = drawn.convert("RGB").getpixel((int(0.25 * width) + 1, height // 2))
        on_b = drawn.convert("RGB").getpixel((int(0.05 * width) + 1, height // 2))
        inside = drawn.convert("RGB").getpixel((width // 2, int(0.4 * height)))
    assert _near(on_a, ZONE_COLOURS[0])
    assert _near(on_b, ZONE_COLOURS[1])
    assert _near(inside, (90, 90, 90))


def _near(pixel: object, colour: tuple[int, int, int]) -> bool:
    """Compare a JPEG pixel with a colour, allowing for compression.

    Returns:
        True if every channel is within 40 of the colour's.
    """
    assert isinstance(pixel, tuple)
    return all(abs(int(got) - want) <= 40 for got, want in zip(pixel, colour, strict=True))


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("", "no source"),
        ("https://example.org/x.jpg", "no source"),
        (f"visa:{IMAGE}", "#zones or #mask"),
        (f"visa:{IMAGE}#mask=two", "#zones or #mask"),
        (f"visa:{IMAGE}#mask=5", "no pixel"),
        ("visa:pcb9/Data/Images/Anomaly/404.JPG#mask=2", "404.JPG"),
        ("visa:../outside.JPG#zones", "outside"),
    ],
)
def test_a_figure_that_cannot_be_built_is_refused(
    visa: Path, tmp_path: Path, source: str, reason: str
) -> None:
    """A source outside the grammar, or one the data cannot satisfy, raises with the reason."""
    with pytest.raises(FigureError, match=reason):
        build_figure(figure(source), visa_dir=visa, zones=(zone(),), out_dir=tmp_path)


def test_a_zone_figure_of_a_part_without_zones_is_refused(visa: Path, tmp_path: Path) -> None:
    """Zones cannot be drawn for a part the specification gives none."""
    with pytest.raises(FigureError, match="no zones"):
        build_figure(figure(f"visa:{IMAGE}#zones"), visa_dir=visa, zones=(), out_dir=tmp_path)


def test_every_figure_of_a_source_is_built_beside_it(visa: Path, tmp_path: Path) -> None:
    """The figures a Markdown source names are written relative to it, its zones drawn."""
    source = tmp_path / "spec" / "fake.md"
    source.parent.mkdir()
    source.write_text(_MARKDOWN, encoding="utf-8")

    built = build_figures(source, visa_dir=visa)

    assert built == [
        tmp_path / "spec" / "figures" / "zones.jpg",
        tmp_path / "spec" / "figures" / "scratch.jpg",
    ]
    assert all(path.is_file() for path in built)


_MARKDOWN = f"""\
# Fake specification

Written for a test.

## 1 Calibration and zones

| Part | Board width (mm) | Imaged width (mm) | Imaged height (mm) |
| --- | --- | --- | --- |
| PCB9 | 40.0 | 50.0 | 37.5 |

| Part | Zone | Covers | x0 | y0 | x1 | y1 |
| --- | --- | --- | --- | --- | --- | --- |
| PCB9 | A | The board | 0.1 | 0.1 | 0.9 | 0.9 |

![The zones.](figures/zones.jpg "visa:{IMAGE}#zones")

## 2 Acceptance criteria for part PCB9

### 2.1 Scratch

A scratch is rejected.

| Clause | Defect class | Zone | Limit | Disposition |
| --- | --- | --- | --- | --- |
| 2.1 | scratch | Any | Not permitted | Reject |

![A scratch.](figures/scratch.jpg "visa:{IMAGE}#mask=2")
"""


@pytest.mark.data
def test_the_tracked_figures_are_what_the_fetched_data_builds(tmp_path: Path) -> None:
    """Rebuilt from `data/visa`, every figure of the demo specification is the tracked file."""
    specs = Path(__file__).resolve().parents[2] / "specs"
    source = tmp_path / "pcb-spec.md"
    source.write_text((specs / "pcb-spec.md").read_text(encoding="utf-8"), encoding="utf-8")

    built = build_figures(source, visa_dir=Settings().visa_dir.resolve())

    assert len(built) == 14
    for path in built:
        assert path.read_bytes() == (specs / "figures" / path.name).read_bytes(), path.name
