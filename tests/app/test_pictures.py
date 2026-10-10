"""Tests for the pictures the console draws: thumbnails, heatmaps and specification pages."""

import io
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from spec_to_inspector.app.pictures import PictureError, heatmap, pdf_page, thumbnail
from spec_to_inspector.app.runs import open_run
from tests.app.console_fakes import BATCH, World, write_world
from tests.judge.run_fakes import CATEGORY

SPEC_PDF = Path("specs/pcb-spec.pdf")


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The fake world, written once for the module.

    Returns:
        Where its files are.
    """
    return write_world(tmp_path_factory.mktemp("pictures"))


def _decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_a_thumbnail_keeps_the_photograph_in_proportion(tmp_path: Path) -> None:
    """A thumbnail is a JPEG of the width asked for and the photograph's own shape."""
    source = tmp_path / "board.png"
    Image.new("RGB", (1000, 800), (20, 110, 0)).save(source)

    image = _decode(thumbnail(source, width=250))

    assert image.format == "JPEG"
    assert image.size == (250, 200)


def test_a_thumbnail_is_never_larger_than_the_photograph(tmp_path: Path) -> None:
    """A small photograph is not blown up."""
    source = tmp_path / "small.png"
    Image.new("RGB", (120, 90), (20, 110, 0)).save(source)

    assert _decode(thumbnail(source, width=400)).size == (120, 90)


def test_a_thumbnail_of_a_file_that_is_not_a_picture_is_refused(tmp_path: Path) -> None:
    """A file PIL cannot read gives an error in words, not a traceback."""
    source = tmp_path / "board.jpg"
    source.write_text("not a picture", encoding="utf-8")

    with pytest.raises(PictureError, match=r"board\.jpg"):
        thumbnail(source, width=250)
    with pytest.raises(PictureError, match=r"absent\.jpg"):
        thumbnail(tmp_path / "absent.jpg", width=250)


def test_the_heatmap_covers_the_crop_and_is_hottest_on_the_region(world: World) -> None:
    """The heatmap is the crop's own rectangle, tinted on the region and the board elsewhere."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("scratch")
    region = board.result.regions[0]
    assert region.crop is not None
    assert region.crop_box is not None
    with Image.open(board.directory / region.crop) as crop:
        crop_size = crop.size
        board_colour = np.asarray(crop.convert("RGB")).astype(int)[2, 2]

    image = _decode(heatmap(board.directory, board.result, region))
    pixels = np.asarray(image.convert("RGB")).astype(int)

    assert image.format == "PNG"
    assert image.size == crop_size
    centre_x = round(region.centroid[0]) - region.crop_box.x
    centre_y = round(region.centroid[1]) - region.crop_box.y
    hot = pixels[centre_y, centre_x]
    cool = pixels[2, 2]
    assert np.abs(hot - board_colour).max() > 60
    assert np.abs(cool - board_colour).max() < 20


def test_a_region_without_a_crop_has_no_heatmap(world: World) -> None:
    """A region the run wrote no crop for cannot be drawn, and says so."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("scratch")
    bare = board.result.regions[0].model_copy(update={"crop": None, "crop_box": None})

    with pytest.raises(PictureError, match="no crop"):
        heatmap(board.directory, board.result, bare)


def test_a_specification_page_is_drawn_at_the_width_asked_for() -> None:
    """A page of the tracked specification comes back as an A4 portrait PNG."""
    image = _decode(pdf_page(SPEC_PDF, 3, width=600))

    assert image.format == "PNG"
    assert image.size[0] == 600
    assert image.size[1] == pytest.approx(600 * 297 / 210, abs=3)


@pytest.mark.parametrize("page", [0, 7, 99])
def test_a_page_the_document_does_not_have_is_refused(page: int) -> None:
    """The demo specification has six pages; any other number is an error in words."""
    with pytest.raises(PictureError, match="has 6 pages"):
        pdf_page(SPEC_PDF, page, width=600)


def test_a_file_that_is_not_a_pdf_has_no_pages(tmp_path: Path) -> None:
    """A file pdfium cannot open gives an error in words."""
    path = tmp_path / "notes.pdf"
    path.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(PictureError, match=r"notes\.pdf"):
        pdf_page(path, 1, width=600)


@pytest.mark.parametrize("damage", [b"", b"\x93NUMPY cut short", b"not an array at all"])
def test_a_damaged_anomaly_map_is_refused_in_words(
    world: World, tmp_path: Path, damage: bytes
) -> None:
    """An anomaly map that was cut short gives an error in words, not a traceback."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("scratch")
    directory = tmp_path / "scratch"
    shutil.copytree(board.directory, directory)
    (directory / board.result.anomaly_map).write_bytes(damage)

    with pytest.raises(PictureError, match="cannot be read"):
        heatmap(directory, board.result, board.result.regions[0])


def test_a_crop_named_outside_the_board_directory_is_not_drawn(
    world: World, tmp_path: Path
) -> None:
    """A result whose crop points out of its directory is refused, whatever the file is."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("scratch")
    region = board.result.regions[0]
    outside = region.model_copy(update={"crop": "../two/crops/region-001.png"})
    tampered = board.result.model_copy(update={"regions": [outside]})

    with pytest.raises(PictureError, match="outside"):
        heatmap(board.directory, tampered, outside)
