"""Tests for training PatchCore on a category and recording what it took."""

from pathlib import Path

import pytest
import torch
from anomalib.engine import SingleXPUStrategy, XPUAccelerator

from spec_to_inspector.anomaly.infer import AnomalyModel
from spec_to_inspector.anomaly.records import TrainRecord
from spec_to_inspector.anomaly.train import (
    CHECKPOINT_NAME,
    TRAIN_RECORD_NAME,
    ModelNotTrainedError,
    engine_placement,
    load_train_record,
    model_dir,
    train_category,
)
from spec_to_inspector.settings import DeviceKind
from tests.anomaly.fakes import write_trainable_visa


def test_a_categorys_model_lives_under_patchcore(tmp_path: Path) -> None:
    """The memory bank and its record have one documented place per category."""
    assert model_dir(tmp_path / "models", "pcb4") == tmp_path / "models" / "patchcore" / "pcb4"
    assert CHECKPOINT_NAME == "model.ckpt"
    assert TRAIN_RECORD_NAME == "train.json"


def test_a_missing_model_says_how_to_train_it(tmp_path: Path) -> None:
    """Loading a record that is not there names the command that makes it."""
    with pytest.raises(ModelNotTrainedError, match="spec-to-inspector train --category pcb4"):
        load_train_record(tmp_path / "models", "pcb4")


def test_the_laptop_keeps_lightnings_one_gpu() -> None:
    """On CUDA the Engine is asked for what it was always asked for."""
    assert engine_placement("cuda") == {"accelerator": "gpu", "devices": 1}


def test_the_cpu_is_lightnings_own_accelerator() -> None:
    """On the CPU the Engine needs nothing of Anomalib's."""
    assert engine_placement("cpu") == {"accelerator": "cpu", "devices": 1}


def test_an_intel_card_is_named_by_a_list_so_it_is_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anomalib's accelerator reads `devices=1` as the card numbered 1, the judge's card."""
    monkeypatch.setattr(torch.xpu, "is_available", lambda: True)

    placement = engine_placement("xpu")

    assert isinstance(placement["accelerator"], XPUAccelerator)
    assert isinstance(placement["strategy"], SingleXPUStrategy)
    assert placement["devices"] == [0]
    chosen = XPUAccelerator.parse_devices(placement["devices"])
    assert XPUAccelerator.get_parallel_devices(chosen) == [torch.device("xpu", 0)]
    assert placement["strategy"].root_device == torch.device("xpu", 0)


@pytest.mark.xpu
@pytest.mark.parametrize("device", ["xpu", "cpu"])
def test_training_and_scoring_run_on_the_device_asked_for(
    tmp_path: Path, device: DeviceKind
) -> None:
    """Twenty images train on the device, the record says which, and the model scores there."""
    visa = tmp_path / "data" / "visa"
    models = tmp_path / "models"
    write_trainable_visa(visa)

    record = train_category("pcb1", visa_dir=visa, models_dir=models, num_workers=2, device=device)
    model = AnomalyModel.load(models, "pcb1", device=device)
    scores, maps = model.score(torch.rand(1, 3, 256, 256))

    assert record.device.kind == device
    assert record.memory_bank_rows > 0
    assert scores.device.type == device
    assert scores.shape == (1,)
    assert maps.shape == (1, 256, 256)
    if device == "xpu":
        assert scores.device.index == 0
        assert record.peak_allocated_bytes > 0
        assert "B70" in record.device.name


@pytest.mark.gpu
def test_training_on_20_images_writes_the_model_and_its_record(tmp_path: Path) -> None:
    """Twenty normal images give a checkpoint, thresholds with their provenance, and metrics."""
    visa = tmp_path / "data" / "visa"
    models = tmp_path / "models"
    write_trainable_visa(visa)

    record = train_category("pcb1", visa_dir=visa, models_dir=models, num_workers=2)

    base = model_dir(models, "pcb1")
    assert sorted(p.name for p in base.iterdir()) == [CHECKPOINT_NAME, TRAIN_RECORD_NAME]
    assert sorted(p.name for p in base.parent.iterdir()) == ["pcb1"]
    assert load_train_record(models, "pcb1") == record
    assert TrainRecord.model_validate_json((base / TRAIN_RECORD_NAME).read_text()) == record
    assert record.checkpoint == CHECKPOINT_NAME
    assert record.checkpoint_bytes == (base / CHECKPOINT_NAME).stat().st_size

    assert record.category == "pcb1"
    assert (record.train_images, record.test_good, record.test_bad) == (20, 3, 3)
    assert record.model.backbone == "wide_resnet50_2"
    assert record.model.weights == "timm/wide_resnet50_2.racm_in1k"
    assert record.model.image_size == (256, 256)
    assert record.model.variant == "SingleCopyPatchcore"
    assert record.model.precision == "float32"
    assert record.model.tf32 is False
    assert record.embedding_rows == 20 * 32 * 32
    assert (record.memory_bank_rows, record.memory_bank_dims) == (2048, 1536)

    thresholds = record.thresholds
    assert thresholds.method == "anomalib.metrics.F1AdaptiveThreshold"
    assert thresholds.val_split_mode == "same_as_test"
    assert (thresholds.split_images, thresholds.split_images_in_test) == (6, 6)
    assert thresholds.tuned_on_test
    assert thresholds.image_min <= thresholds.image <= thresholds.image_max
    assert thresholds.pixel_min <= thresholds.pixel <= thresholds.pixel_max

    assert record.metrics.image_auroc == 1.0
    assert record.metrics.pixel_auroc > 0.9
    for phase in (record.embed, record.coreset, record.validate_split, record.test):
        assert phase.seconds > 0
        assert phase.peak_allocated_bytes > 0
        assert phase.peak_reserved_bytes >= phase.peak_allocated_bytes
    assert record.peak_allocated_bytes == max(
        p.peak_allocated_bytes
        for p in (record.embed, record.coreset, record.validate_split, record.test)
    )
    assert record.fit_seconds >= record.embed.seconds + record.coreset.seconds
    assert record.device.capability == (12, 0)
    assert set(record.versions) == {"anomalib", "lightning", "timm", "torch", "torchvision"}


@pytest.mark.gpu
def test_training_again_replaces_the_model_whole(tmp_path: Path) -> None:
    """A second training leaves one checkpoint and one record, never a `-v1` beside them."""
    visa = tmp_path / "data" / "visa"
    models = tmp_path / "models"
    write_trainable_visa(visa, train=4)
    first = train_category("pcb1", visa_dir=visa, models_dir=models, num_workers=2)

    second = train_category("pcb1", visa_dir=visa, models_dir=models, num_workers=2)

    base = model_dir(models, "pcb1")
    assert sorted(p.name for p in base.iterdir()) == [CHECKPOINT_NAME, TRAIN_RECORD_NAME]
    assert sorted(p.name for p in base.parent.iterdir()) == ["pcb1"]
    assert second.created_at >= first.created_at
    assert second.thresholds == first.thresholds
    assert second.metrics == first.metrics
