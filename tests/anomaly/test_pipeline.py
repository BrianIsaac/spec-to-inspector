"""The anomaly model end to end on the GPU: train on 20 images, score the test split.

These need the GPU and the backbone's pretrained weights, but no fetched data:
the images are a synthetic board with a planted defect.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest
from anomalib.data import ImageBatch, Visa
from anomalib.engine import Engine
from PIL import Image

from spec_to_inspector.anomaly.infer import (
    CROPS_DIR,
    MAP_NAME,
    MASK_NAME,
    REGIONS_NAME,
    RESULT_NAME,
    RUN_INDEX_NAME,
    AnomalyModel,
    InferenceOptions,
    load_anomaly_map,
    load_result,
    load_run_index,
    run_dir,
    run_inference,
    visa_test_items,
)
from spec_to_inspector.anomaly.model import HostBufferedPatchcore
from spec_to_inspector.anomaly.records import RunIndex, TrainRecord
from spec_to_inspector.anomaly.train import CHECKPOINT_NAME, model_dir, train_category
from tests.anomaly.fakes import DEFECT, write_trainable_visa

pytestmark = pytest.mark.gpu

SIZE = (192, 256)


class Trained:
    """A category trained once for the module, with its run on the test split."""

    def __init__(self, root: Path) -> None:
        """Train on 20 synthetic images and score the six test images.

        Args:
            root: A directory for the data, the model and the run.
        """
        self.visa = root / "data" / "visa"
        self.models = root / "models"
        self.runs = root / "runs"
        write_trainable_visa(self.visa, size=SIZE)
        self.record: TrainRecord = train_category(
            "pcb1", visa_dir=self.visa, models_dir=self.models, num_workers=2
        )
        self.model = AnomalyModel.load(self.models, "pcb1")
        self.output = run_dir(self.runs, "pcb1")
        self.index: RunIndex = run_inference(
            self.model,
            visa_test_items(self.visa, "pcb1"),
            self.output,
            options=InferenceOptions(batch_size=4, num_workers=2, crop_min_side=64),
        )


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> Trained:
    """Train and score once for every test in this module.

    Returns:
        The trained category and its run.
    """
    return Trained(tmp_path_factory.mktemp("pipeline"))


def test_the_run_directory_has_the_documented_layout(trained: Trained) -> None:
    """`runs/<category>/test/` holds the index and one directory per test image."""
    ids = ["good-0020", "good-0021", "good-0022", "bad-000", "bad-001", "bad-002"]

    assert trained.output == trained.runs / "pcb1" / "test"
    assert sorted(p.name for p in trained.output.iterdir()) == sorted([RUN_INDEX_NAME, *ids])
    assert load_run_index(trained.output) == trained.index
    assert [entry.image_id for entry in trained.index.entries] == ids
    assert trained.index.thresholds == trained.record.thresholds
    for image_id in ids:
        names = {p.name for p in (trained.output / image_id).iterdir()}
        assert {RESULT_NAME, MAP_NAME, MASK_NAME, REGIONS_NAME} <= names
        assert names <= {RESULT_NAME, MAP_NAME, MASK_NAME, REGIONS_NAME, CROPS_DIR}


def test_every_sidecar_agrees_with_its_files(trained: Trained) -> None:
    """Score, thresholds, sizes, mask, label image and crops are consistent per image."""
    height, width = SIZE
    for entry in trained.index.entries:
        directory = trained.output / entry.image_id
        result = load_result(directory)
        source = np.asarray(Image.open(result.image).convert("RGB"))

        assert (result.width, result.height) == (width, height)
        assert (result.map_width, result.map_height) == (256, 256)
        assert result.image_threshold == trained.record.thresholds.image
        assert result.pixel_threshold == trained.record.thresholds.pixel
        assert result.predicted_anomalous == (result.score > result.image_threshold)
        assert result.visa_image is not None
        assert Path(result.image).is_file()

        anomaly_map = load_anomaly_map(directory, result)
        assert anomaly_map.shape == (256, 256)
        assert anomaly_map.dtype == np.float32
        mask = cv2.imread(str(directory / result.mask), cv2.IMREAD_UNCHANGED)
        labels = cv2.imread(str(directory / result.regions_image), cv2.IMREAD_UNCHANGED)
        assert mask is not None
        assert labels is not None
        assert mask.shape == labels.shape == (height, width)
        at_source = load_anomaly_map(directory, result, at_source=True)
        assert np.array_equal(mask == 255, at_source > result.pixel_threshold)
        assert np.array_equal(labels > 0, mask == 255)
        assert (
            sorted(np.unique(labels).tolist())
            == [0, *(r.index for r in result.regions)][0 if (labels == 0).any() else 1 :]
        )
        for region in result.regions:
            assert region.crop is not None
            assert region.crop_box is not None
            box = region.crop_box
            crop = np.asarray(Image.open(directory / region.crop))
            assert np.array_equal(
                crop, source[box.y : box.y + box.height, box.x : box.x + box.width]
            )


def test_the_planted_defect_is_found_where_it_was_planted(trained: Trained) -> None:
    """Anomalous images score above the threshold and region 1 lies on the defect."""
    rows, columns = DEFECT
    for entry in trained.index.entries:
        result = load_result(trained.output / entry.image_id)
        if result.label == "good":
            assert not result.predicted_anomalous
            continue
        assert result.predicted_anomalous
        assert result.ground_truth_mask is not None
        assert Path(result.ground_truth_mask).is_file()
        top = result.regions[0]
        x, y = top.peak_xy
        assert columns.start - 8 <= x < columns.stop + 8
        assert rows.start - 8 <= y < rows.stop + 8
        assert top.bbox.x < columns.stop
        assert top.bbox.x + top.bbox.width > columns.start
        assert top.bbox.y < rows.stop
        assert top.bbox.y + top.bbox.height > rows.start


def test_the_runs_auroc_is_the_training_records(trained: Trained) -> None:
    """Scoring the test split again gives the image AUROC Anomalib's test pass gave."""
    assert (trained.index.labelled_good, trained.index.labelled_bad) == (3, 3)
    assert trained.index.image_auroc == pytest.approx(trained.record.metrics.image_auroc)


def test_scores_and_maps_equal_anomalibs_own_predictions(trained: Trained) -> None:
    """Our raw scores, normalised, are the scores Anomalib's Engine predicts for the images.

    The images go through in Anomalib's order and batch size: float32 rounding
    in PatchCore's distances depends on which images share a batch, and moves
    a normalised score by about 1e-5 otherwise.
    """
    checkpoint = model_dir(trained.models, "pcb1") / CHECKPOINT_NAME
    module = HostBufferedPatchcore.load_from_checkpoint(checkpoint)
    datamodule = Visa(root=trained.visa, category="pcb1", eval_batch_size=4, num_workers=2)
    engine = Engine(default_root_dir=trained.runs / "engine", accelerator="gpu", devices=1)

    batches = engine.predict(model=module, datamodule=datamodule)

    assert batches is not None
    theirs: list[tuple[str, float, np.ndarray]] = []
    for batch in batches:
        assert isinstance(batch, ImageBatch)
        assert batch.image_path is not None
        assert batch.pred_score is not None
        assert batch.anomaly_map is not None
        for path, score, anomaly_map in zip(
            batch.image_path, batch.pred_score, batch.anomaly_map, strict=True
        ):
            theirs.append((Path(path).name, float(score), anomaly_map.squeeze().cpu().numpy()))
    by_name = {item.path.name: item for item in visa_test_items(trained.visa, "pcb1")}
    output = trained.runs / "pcb1" / "parity"
    index = run_inference(
        trained.model,
        [by_name[name] for name, _, _ in theirs],
        output,
        options=InferenceOptions(batch_size=4, num_workers=2),
    )

    thresholds = trained.record.thresholds
    assert len(theirs) == len(index.entries) == 6
    for entry, (_, score, anomaly_map) in zip(index.entries, theirs, strict=True):
        directory = output / entry.image_id
        result = load_result(directory)
        assert result.score_normalised == pytest.approx(score, abs=1e-6)
        ours = load_anomaly_map(directory, result)
        normalised = np.clip(
            (ours - thresholds.pixel) / (thresholds.pixel_max - thresholds.pixel_min) + 0.5, 0, 1
        )
        assert np.allclose(normalised, anomaly_map, atol=1e-6)
