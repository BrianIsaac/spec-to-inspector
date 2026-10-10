"""Tests for inference's outputs: the sidecar, the map, the mask, the regions and the crops."""

import json
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import pytest
import torch
from PIL import Image
from torchvision.transforms.v2 import Resize

from spec_to_inspector.anomaly.infer import (
    CROPS_DIR,
    MAP_NAME,
    MASK_NAME,
    REGIONS_NAME,
    RESULT_NAME,
    RUN_INDEX_NAME,
    InferenceItem,
    InferenceOptions,
    load_anomaly_map,
    load_result,
    load_run_index,
    run_dir,
    run_inference,
    visa_test_items,
    write_image_result,
)
from spec_to_inspector.anomaly.records import Box, ImageResult, Thresholds
from spec_to_inspector.anomaly.regions import upsample
from spec_to_inspector.anomaly.split import SPLIT_ROOT, write_split
from tests.anomaly.fakes import write_visa

WIDTH, HEIGHT = 400, 300


def _thresholds(image: float = 30.0, pixel: float = 25.0) -> Thresholds:
    return Thresholds(
        image=image,
        pixel=pixel,
        image_min=10.0,
        image_max=60.0,
        pixel_min=2.0,
        pixel_max=52.0,
        method="anomalib.metrics.F1AdaptiveThreshold",
        val_split_mode="same_as_test",
        split_images=4,
        split_images_in_test=4,
        tuned_on_test=True,
    )


def _image(path: Path) -> np.ndarray:
    """Write a 400 x 300 image whose pixels encode their position, losslessly.

    Returns:
        The image as (rows, columns, RGB).
    """
    rows, columns = np.mgrid[0:HEIGHT, 0:WIDTH]
    rgb = np.stack([rows % 256, columns % 256, (rows + columns) % 256], axis=-1).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(path)
    return rgb


def _map(*blobs: tuple[slice, slice, float]) -> np.ndarray:
    """A 256 x 256 raw anomaly map, flat at 5 with some hotter rectangles.

    Returns:
        The map.
    """
    anomaly_map = np.full((256, 256), 5.0, dtype=np.float32)
    for rows, columns, value in blobs:
        anomaly_map[rows, columns] = value
    return anomaly_map


def _write(
    tmp_path: Path,
    anomaly_map: np.ndarray,
    *,
    score: float = 41.5,
    mask_path: Path | None = None,
    **options: float | str | bool,
) -> tuple[ImageResult, Path]:
    source = tmp_path / "source" / "000.png"
    _image(source)
    directory = tmp_path / "out" / "bad-000"
    directory.mkdir(parents=True)
    result = write_image_result(
        InferenceItem(
            image_id="bad-000",
            path=source,
            label="bad",
            mask_path=mask_path,
            visa_image="pcb4/Data/Images/Anomaly/000.JPG",
        ),
        category="pcb4",
        score=score,
        anomaly_map=anomaly_map,
        thresholds=_thresholds(),
        directory=directory,
        options=InferenceOptions.model_validate(options),
        map_cell=(8, 8),
    )
    return result, directory


def test_the_sidecar_carries_the_score_the_thresholds_and_the_files(tmp_path: Path) -> None:
    """One image's directory holds the sidecar, the map, the mask, the labels and the crops."""
    result, directory = _write(tmp_path, _map((slice(100, 140), slice(64, 128), 40.0)))

    assert sorted(p.name for p in directory.iterdir()) == sorted(
        [RESULT_NAME, MAP_NAME, MASK_NAME, REGIONS_NAME, CROPS_DIR]
    )
    assert load_result(directory) == result
    raw = json.loads((directory / RESULT_NAME).read_text())
    assert raw["schema_version"] == 1
    assert result.category == "pcb4"
    assert result.image_id == "bad-000"
    assert result.image == str(tmp_path / "source" / "000.png")
    assert result.visa_image == "pcb4/Data/Images/Anomaly/000.JPG"
    assert (result.width, result.height) == (WIDTH, HEIGHT)
    assert (result.map_width, result.map_height) == (256, 256)
    assert result.label == "bad"
    assert result.score == 41.5
    assert result.image_threshold == 30.0
    assert result.pixel_threshold == 25.0
    assert result.region_threshold == 30.0
    assert result.region_threshold_source == "image"
    assert result.predicted_anomalous
    assert result.score_normalised == pytest.approx(0.5 + 11.5 / 50)
    assert (result.anomaly_map, result.mask, result.regions_image) == (
        MAP_NAME,
        MASK_NAME,
        REGIONS_NAME,
    )


def test_a_score_at_the_threshold_is_not_anomalous(tmp_path: Path) -> None:
    """An image is anomalous only above the image threshold, as in Anomalib."""
    source = tmp_path / "000.png"
    _image(source)
    directory = tmp_path / "out"
    directory.mkdir()

    result = write_image_result(
        InferenceItem(image_id="x", path=source),
        category="pcb4",
        score=30.0,
        anomaly_map=_map(),
        thresholds=_thresholds(),
        directory=directory,
        options=InferenceOptions(),
        map_cell=(8, 8),
    )

    assert not result.predicted_anomalous
    assert result.score_normalised == 0.5
    assert result.label is None
    assert result.regions == []
    assert result.mask_pixels == 0
    assert not (directory / CROPS_DIR).exists()


def test_the_stored_map_is_the_raw_map_at_the_models_resolution(tmp_path: Path) -> None:
    """The map is kept as float32 in raw units, and a helper stretches it to the source."""
    anomaly_map = _map((slice(100, 140), slice(64, 128), 40.0))
    result, directory = _write(tmp_path, anomaly_map)

    stored = np.load(directory / MAP_NAME)
    assert stored.dtype == np.float32
    assert np.array_equal(stored, anomaly_map)
    assert result.map_max == 40.0
    assert np.array_equal(load_anomaly_map(directory, result), anomaly_map)
    at_source = load_anomaly_map(directory, result, at_source=True)
    assert at_source.shape == (HEIGHT, WIDTH)
    assert np.array_equal(at_source, upsample(anomaly_map, width=WIDTH, height=HEIGHT))


def test_the_mask_is_in_source_pixels_and_follows_from_the_map(tmp_path: Path) -> None:
    """The mask has the source image's size, holds 0 and 255, and is the stretched map's cut."""
    result, directory = _write(tmp_path, _map((slice(100, 140), slice(64, 128), 40.0)))

    mask = cv2.imread(str(directory / MASK_NAME), cv2.IMREAD_UNCHANGED)
    assert mask is not None
    assert mask.shape == (HEIGHT, WIDTH)
    assert mask.dtype == np.uint8
    assert set(np.unique(mask).tolist()) == {0, 255}
    at_source = load_anomaly_map(directory, result, at_source=True)
    assert np.array_equal(mask == 255, at_source > result.region_threshold)
    assert result.mask_pixels == int((mask == 255).sum())
    # The blob covers map rows 100..139 and columns 64..127: about 47 x 100 source pixels.
    region = result.regions[0]
    assert abs(region.bbox.x - 100) <= 2
    assert abs(region.bbox.y - 117) <= 2
    assert abs(region.bbox.width - 100) <= 3
    assert abs(region.bbox.height - 47) <= 3


def test_the_label_image_numbers_each_regions_pixels(tmp_path: Path) -> None:
    """Region k's pixels hold k in the 16-bit label image; the mask is their union."""
    result, directory = _write(
        tmp_path,
        _map((slice(100, 140), slice(64, 128), 40.0), (slice(20, 30), slice(200, 220), 48.0)),
    )

    labels = cv2.imread(str(directory / REGIONS_NAME), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(directory / MASK_NAME), cv2.IMREAD_UNCHANGED)
    assert labels is not None
    assert mask is not None
    assert labels.dtype == np.uint16
    assert labels.shape == (HEIGHT, WIDTH)
    assert [r.index for r in result.regions] == [1, 2]
    assert result.regions[0].peak_score == pytest.approx(48.0)
    assert result.regions[1].peak_score == pytest.approx(40.0)
    for region in result.regions:
        inside = labels == region.index
        assert int(inside.sum()) == region.area_px
        rows, columns = np.nonzero(inside)
        assert (columns.min(), rows.min()) == (region.bbox.x, region.bbox.y)
        assert (columns.max() - columns.min() + 1) == region.bbox.width
        assert (rows.max() - rows.min() + 1) == region.bbox.height
    assert np.array_equal(labels > 0, mask == 255)


def test_each_crop_is_the_source_images_own_pixels(tmp_path: Path) -> None:
    """A crop is cut from the source at its recorded rectangle, losslessly, and named by rank."""
    result, directory = _write(
        tmp_path,
        _map((slice(100, 140), slice(64, 128), 40.0), (slice(20, 30), slice(200, 220), 48.0)),
        crop_min_side=64,
    )
    source = np.asarray(Image.open(tmp_path / "source" / "000.png").convert("RGB"))

    assert [r.crop for r in result.regions] == [
        f"{CROPS_DIR}/region-001.png",
        f"{CROPS_DIR}/region-002.png",
    ]
    for region in result.regions:
        assert region.crop is not None
        assert region.crop_box is not None
        box = region.crop_box
        crop = np.asarray(Image.open(directory / region.crop))
        assert crop.shape == (box.height, box.width, 3)
        assert np.array_equal(crop, source[box.y : box.y + box.height, box.x : box.x + box.width])
        assert box.x <= region.bbox.x
        assert box.y <= region.bbox.y
        assert box.x + box.width >= region.bbox.x + region.bbox.width
        assert box.y + box.height >= region.bbox.y + region.bbox.height


def test_crops_stop_at_the_limit_but_every_region_is_recorded(tmp_path: Path) -> None:
    """Beyond the crop limit a region keeps its geometry and has no crop."""
    result, directory = _write(
        tmp_path,
        _map((slice(100, 140), slice(64, 128), 40.0), (slice(20, 30), slice(200, 220), 48.0)),
        max_crops=1,
    )

    assert [r.crop for r in result.regions] == [f"{CROPS_DIR}/region-001.png", None]
    assert result.regions[1].crop_box is None
    assert [p.name for p in (directory / CROPS_DIR).iterdir()] == ["region-001.png"]


def test_small_regions_can_be_left_out(tmp_path: Path) -> None:
    """With a minimum area, a speck is in neither the regions, the labels nor the mask."""
    anomaly_map = _map(
        (slice(100, 140), slice(64, 128), 40.0), (slice(20, 22), slice(200, 202), 200.0)
    )
    kept, _ = _write(tmp_path / "all", anomaly_map)
    result, directory = _write(tmp_path / "filtered", anomaly_map, min_region_area=50)

    mask = cv2.imread(str(directory / MASK_NAME), cv2.IMREAD_UNCHANGED)
    assert mask is not None
    assert len(kept.regions) == 2
    assert kept.regions[0].area_px < 50
    assert len(result.regions) == 1
    assert result.regions[0].peak_score == pytest.approx(40.0)
    assert result.mask_pixels == result.regions[0].area_px == int((mask == 255).sum())


class _StubModel:
    """A scorer that gives each image its mean red value and a map with one hot block."""

    category = "pcb4"
    thresholds = _thresholds(image=0.5, pixel=25.0)
    resize = Resize((256, 256), antialias=True)
    map_cell = (8, 8)

    def __init__(self) -> None:
        self.batches: list[int] = []

    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        self.batches.append(images.shape[0])
        assert images.shape[1:] == (3, 256, 256)
        maps = torch.full((images.shape[0], 256, 256), 0.1)
        maps[:, 100:140, 64:128] = 40.0
        return images[:, 0].mean(dim=(1, 2)), maps


def _items(tmp_path: Path) -> list[InferenceItem]:
    items: list[InferenceItem] = []
    boards: list[tuple[Literal["good", "bad"], int]] = [
        ("good", 20),
        ("bad", 200),
        ("bad", 230),
        ("good", 60),
    ]
    for index, (label, red) in enumerate(boards):
        path = tmp_path / "source" / f"{index:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((HEIGHT, WIDTH, 3), red, dtype=np.uint8)).save(path)
        items.append(InferenceItem(image_id=f"{label}-{index:03d}", path=path, label=label))
    return items


def test_a_run_writes_one_directory_per_image_and_an_index(tmp_path: Path) -> None:
    """A batch of images becomes a run directory: an index and a sidecar per image."""
    model = _StubModel()
    output = tmp_path / "runs" / "pcb4" / "test"

    index = run_inference(
        model, _items(tmp_path), output, options=InferenceOptions(batch_size=3, num_workers=0)
    )

    assert model.batches == [3, 1]
    assert sorted(p.name for p in output.iterdir()) == sorted(
        [RUN_INDEX_NAME, "good-000", "bad-001", "bad-002", "good-003"]
    )
    assert load_run_index(output) == index
    assert index.category == "pcb4"
    assert index.images == 4
    assert (index.labelled_good, index.labelled_bad) == (2, 2)
    assert index.image_auroc == 1.0
    assert index.thresholds == model.thresholds
    assert index.options.batch_size == 3
    assert [e.image_id for e in index.entries] == ["good-000", "bad-001", "bad-002", "good-003"]
    assert [e.predicted_anomalous for e in index.entries] == [False, True, True, False]
    assert [e.peak_fallback for e in index.entries] == [False] * 4
    assert [e.top_region_on_ground_truth for e in index.entries] == [None] * 4
    assert [e.result for e in index.entries] == [
        f"{e.image_id}/{RESULT_NAME}" for e in index.entries
    ]
    for entry in index.entries:
        result = load_result(output / entry.image_id)
        assert result.score == entry.score
        assert len(result.regions) == entry.regions == 1
    assert load_result(output / "bad-001").score == pytest.approx(200 / 255, abs=1e-6)


def test_a_run_replaces_the_previous_run_whole(tmp_path: Path) -> None:
    """Running again leaves no file of the earlier run and no partial directory."""
    output = tmp_path / "runs" / "pcb4" / "test"
    items = _items(tmp_path)
    run_inference(_StubModel(), items, output, options=InferenceOptions(num_workers=0))

    run_inference(_StubModel(), items[:2], output, options=InferenceOptions(num_workers=0))

    assert sorted(p.name for p in output.iterdir()) == sorted(
        [RUN_INDEX_NAME, "good-000", "bad-001"]
    )
    assert [p.name for p in output.parent.iterdir()] == ["test"]


def test_a_run_without_both_labels_has_no_auroc(tmp_path: Path) -> None:
    """AUROC needs normal and anomalous images; without both it is absent, not zero."""
    items = [item.model_copy(update={"label": None}) for item in _items(tmp_path)]

    index = run_inference(
        _StubModel(), items, tmp_path / "run", options=InferenceOptions(num_workers=0)
    )

    assert index.image_auroc is None
    assert (index.labelled_good, index.labelled_bad) == (0, 0)


def test_image_ids_must_be_unique_and_plain(tmp_path: Path) -> None:
    """Two images cannot share a directory, and an id cannot climb out of the run."""
    items = _items(tmp_path)
    twice = [items[0], items[0]]

    with pytest.raises(ValueError, match="good-000"):
        run_inference(
            _StubModel(), twice, tmp_path / "run", options=InferenceOptions(num_workers=0)
        )
    with pytest.raises(ValueError, match="image_id"):
        InferenceItem(image_id="../escape", path=items[0].path)
    assert not (tmp_path / "run").exists()


def test_the_test_splits_items_come_from_the_csv(tmp_path: Path) -> None:
    """The test split's items name the fetched image, its label, its mask and its VisA key."""
    visa = tmp_path / "visa"
    write_visa(visa)
    write_split(visa, ["pcb1"])

    items = visa_test_items(visa, "pcb1")

    assert [i.image_id for i in items] == [
        "good-0003",
        "good-0004",
        "bad-000",
        "bad-001",
        "bad-002",
    ]
    assert [i.label for i in items] == ["good", "good", "bad", "bad", "bad"]
    assert items[0].path == visa / "pcb1/Data/Images/Normal/0003.JPG"
    assert items[0].mask_path is None
    assert items[2].path == visa / "pcb1/Data/Images/Anomaly/000.JPG"
    assert items[2].visa_image == "pcb1/Data/Images/Anomaly/000.JPG"
    assert items[2].mask_path == visa / SPLIT_ROOT / "pcb1/ground_truth/bad/000.png"
    assert run_dir(tmp_path / "runs", "pcb1") == tmp_path / "runs" / "pcb1" / "test"
    assert run_dir(tmp_path / "runs", "pcb1", "line-3") == tmp_path / "runs" / "pcb1" / "line-3"


def test_the_region_threshold_is_the_image_threshold_unless_asked(tmp_path: Path) -> None:
    """By default the map is cut at the image threshold; Anomalib's pixel one is an option."""
    anomaly_map = _map((slice(100, 140), slice(64, 128), 28.0))

    by_image, _ = _write(tmp_path / "image", anomaly_map, peak_fallback=False)
    by_pixel, directory = _write(
        tmp_path / "pixel", anomaly_map, region_threshold="pixel", peak_fallback=False
    )

    assert by_image.region_threshold == by_image.image_threshold == 30.0
    assert by_image.regions == []
    assert (by_pixel.region_threshold, by_pixel.region_threshold_source) == (25.0, "pixel")
    assert len(by_pixel.regions) == 1
    at_source = load_anomaly_map(directory, by_pixel, at_source=True)
    mask = cv2.imread(str(directory / MASK_NAME), cv2.IMREAD_UNCHANGED)
    assert mask is not None
    assert np.array_equal(mask == 255, at_source > 25.0)


def test_a_flagged_image_with_nothing_above_the_threshold_gets_its_peak_patch(
    tmp_path: Path,
) -> None:
    """An anomalous image always has a region: failing all else, the patch of the map's peak."""
    anomaly_map = _map((slice(100, 140), slice(64, 128), 28.0))
    anomaly_map[117, 83] = 29.5

    result, directory = _write(tmp_path, anomaly_map)

    assert result.predicted_anomalous
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.from_peak
    # The peak is in the map cell of rows 112..119 and columns 80..87; the source is
    # 400 x 300, so the cell covers columns 125..137 and rows 131..140.
    assert region.bbox == Box(x=125, y=131, width=13, height=10)
    assert region.area_px == 130
    assert region.centroid == (131.0, 135.5)
    assert region.bbox.x <= region.peak_xy[0] < region.bbox.x + region.bbox.width
    assert region.bbox.y <= region.peak_xy[1] < region.bbox.y + region.bbox.height
    assert region.peak_score <= 29.5
    assert region.crop == f"{CROPS_DIR}/region-001.png"
    labels = cv2.imread(str(directory / REGIONS_NAME), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(directory / MASK_NAME), cv2.IMREAD_UNCHANGED)
    assert labels is not None
    assert mask is not None
    assert int((labels == 1).sum()) == 130
    assert np.array_equal(labels > 0, mask == 255)
    assert result.mask_pixels == 130


def test_the_peak_patch_is_only_for_flagged_images_and_can_be_switched_off(
    tmp_path: Path,
) -> None:
    """An image under the image threshold gets no fallback, and neither does one that opts out."""
    anomaly_map = _map((slice(100, 140), slice(64, 128), 28.0))

    unflagged, _ = _write(tmp_path / "unflagged", anomaly_map, score=29.0)
    opted_out, _ = _write(tmp_path / "opted-out", anomaly_map, peak_fallback=False)

    assert unflagged.regions == []
    assert opted_out.regions == []
    assert opted_out.predicted_anomalous


def test_regions_above_the_threshold_are_not_from_the_peak(tmp_path: Path) -> None:
    """A region found by the threshold says so."""
    result, _ = _write(tmp_path, _map((slice(100, 140), slice(64, 128), 40.0)))

    assert [region.from_peak for region in result.regions] == [False]


def test_each_region_says_whether_it_touches_the_ground_truth(tmp_path: Path) -> None:
    """With a ground-truth mask, a region records whether any of its pixels are on a defect."""
    truth = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    truth[120:160, 100:200] = 255
    mask_path = tmp_path / "truth.png"
    assert cv2.imwrite(str(mask_path), truth)
    anomaly_map = _map(
        (slice(100, 140), slice(64, 128), 40.0), (slice(20, 30), slice(200, 220), 48.0)
    )

    result, _ = _write(tmp_path, anomaly_map, mask_path=mask_path)
    without, _ = _write(tmp_path / "none", anomaly_map)

    assert [region.on_ground_truth for region in result.regions] == [False, True]
    assert result.ground_truth_mask == str(mask_path)
    assert [region.on_ground_truth for region in without.regions] == [None, None]


def test_a_ground_truth_mask_of_another_size_is_refused(tmp_path: Path) -> None:
    """A mask that does not fit its image is an error, not a silent mismatch."""
    mask_path = tmp_path / "truth.png"
    assert cv2.imwrite(str(mask_path), np.zeros((10, 10), dtype=np.uint8))

    with pytest.raises(ValueError, match=r"truth\.png"):
        _write(tmp_path, _map((slice(100, 140), slice(64, 128), 40.0)), mask_path=mask_path)
