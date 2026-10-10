"""Train PatchCore on one VisA category through Anomalib's Engine, and record what it took.

One category's training writes two files, built in a partial directory and
renamed into place, so a failed or killed run leaves the previous model whole:

    <models_dir>/patchcore/<category>/model.ckpt    the Lightning checkpoint: backbone,
                                                    memory bank, thresholds
    <models_dir>/patchcore/<category>/train.json    the `TrainRecord`

The model is Anomalib's PatchCore with its defaults (`wide_resnet50_2`,
layers 2 and 3, 256 x 256, a 10% coreset). The thresholds are Anomalib's
adaptive F1 thresholds, chosen on the datamodule's validation split; with
Anomalib's default for VisA that split is the test set itself, and the record
says so from the data rather than by assumption.
"""

import tempfile
import time
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Final, cast

import torch
from anomalib.callbacks import ModelCheckpoint
from anomalib.data import AnomalibDataset, Visa
from anomalib.engine import Engine
from lightning.pytorch import Callback, LightningModule, Trainer, seed_everything

from spec_to_inspector.anomaly.atomic import atomic_directory
from spec_to_inspector.anomaly.model import HostBufferedPatchcore
from spec_to_inspector.anomaly.records import Metrics, ModelSpec, Phase, Thresholds, TrainRecord
from spec_to_inspector.anomaly.split import write_split
from spec_to_inspector.device import cuda_device

MODEL_NAME: Final = "patchcore"
CHECKPOINT_NAME: Final = "model.ckpt"
TRAIN_RECORD_NAME: Final = "train.json"
DEFAULT_SEED: Final = 0
DEFAULT_BACKBONE: Final = "wide_resnet50_2"
"""Anomalib's default backbone for PatchCore, and the product's."""
IMAGE_SIZE: Final = (256, 256)
"""The model's input as (height, width): Anomalib's default for PatchCore."""
THRESHOLD_METHOD: Final = "anomalib.metrics.F1AdaptiveThreshold"
VERSIONED: Final = ("anomalib", "lightning", "timm", "torch", "torchvision")


class ModelNotTrainedError(RuntimeError):
    """A category's model or its record is not on disk."""


def model_dir(models_dir: Path, category: str) -> Path:
    """Where a category's checkpoint and training record live.

    Args:
        models_dir: The root for trained models.
        category: The category's name.

    Returns:
        The category's model directory.
    """
    return models_dir / MODEL_NAME / category


def load_train_record(models_dir: Path, category: str) -> TrainRecord:
    """Read a category's training record.

    Args:
        models_dir: The root for trained models.
        category: The category's name.

    Returns:
        The record written when the category was trained.

    Raises:
        ModelNotTrainedError: If the record or its checkpoint is missing.
    """
    base = model_dir(models_dir, category)
    record_path = base / TRAIN_RECORD_NAME
    if not record_path.is_file() or not (base / CHECKPOINT_NAME).is_file():
        msg = (
            f"no trained model for {category} under {base}: "
            f"run `spec-to-inspector train --category {category}`"
        )
        raise ModelNotTrainedError(msg)
    return TrainRecord.model_validate_json(record_path.read_text(encoding="utf-8"))


@contextmanager
def _quiet_lightning() -> Generator[None]:
    """Silence two Lightning warnings that are PatchCore's normal state, not faults.

    PatchCore has no optimiser, and its frozen backbone stays in evaluation
    mode while its features are collected.

    Yields:
        Nothing; the warning filters are restored on exit.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r".*configure_optimizers` returned `None`")
        warnings.filterwarnings("ignore", message=r"Found \d+ module\(s\) in eval mode")
        yield


class _PhaseClock(Callback):
    """Marks the ends of a fit's phases, with the peak GPU memory each one reached.

    Lightning calls a callback's `on_validation_start` before the module's own,
    and it is the module's that selects the coreset: so the first mark closes
    the embedding phase, the first validation batch closes coreset selection,
    and the end of validation closes the scoring of the validation split.
    """

    def __init__(self) -> None:
        """Start with no marks."""
        self.marks: dict[str, float] = {}
        self.peaks: dict[str, tuple[int, int]] = {}

    def mark(self, name: str) -> None:
        """Close a phase: note the time and the peak memory since the last mark.

        Args:
            name: The phase that just ended.
        """
        torch.cuda.synchronize()
        self.marks[name] = time.perf_counter()
        self.peaks[name] = (torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
        torch.cuda.reset_peak_memory_stats()

    def phase(self, name: str, since: str) -> Phase:
        """Describe a phase from two marks.

        Args:
            name: The mark that closed the phase.
            since: The mark that opened it.

        Returns:
            The phase's duration and peak memory.
        """
        allocated, reserved = self.peaks[name]
        return Phase(
            seconds=self.marks[name] - self.marks[since],
            peak_allocated_bytes=allocated,
            peak_reserved_bytes=reserved,
        )

    def on_train_start(self, trainer: Trainer, pl_module: LightningModule) -> None:
        """Open the embedding phase."""
        del trainer, pl_module
        self.mark("start")

    def on_validation_start(self, trainer: Trainer, pl_module: LightningModule) -> None:
        """Close the embedding phase; the module selects the coreset next."""
        del trainer, pl_module
        self.mark("embed")

    def on_validation_batch_start(
        self,
        trainer: Trainer,
        pl_module: LightningModule,
        batch: Any,  # noqa: ANN401
        batch_idx: int,
        dataloader_idx: int = 0,
    ) -> None:
        """Close coreset selection when the first validation batch arrives."""
        del trainer, pl_module, batch, dataloader_idx
        if batch_idx == 0:
            self.mark("coreset")

    def on_validation_end(self, trainer: Trainer, pl_module: LightningModule) -> None:
        """Close the scoring of the validation split."""
        del trainer, pl_module
        self.mark("validate")


def _image_paths(dataset: AnomalibDataset) -> set[str]:
    """The image paths of one of the datamodule's subsets."""
    samples = cast("Any", dataset.samples)
    return {str(path) for path in samples["image_path"]}


def _thresholds(model: HostBufferedPatchcore, datamodule: Visa) -> Thresholds:
    """Read the thresholds Anomalib chose, and work out which images it chose them on."""
    post_processor = model.post_processor
    values = {
        name: float(cast("torch.Tensor", getattr(post_processor, name)).item())
        for name in (
            "_image_threshold",
            "_pixel_threshold",
            "image_min",
            "image_max",
            "pixel_min",
            "pixel_max",
        )
    }
    validation = _image_paths(datamodule.val_data)
    test = _image_paths(datamodule.test_data)
    return Thresholds(
        image=values["_image_threshold"],
        pixel=values["_pixel_threshold"],
        image_min=values["image_min"],
        image_max=values["image_max"],
        pixel_min=values["pixel_min"],
        pixel_max=values["pixel_max"],
        method=THRESHOLD_METHOD,
        val_split_mode=str(datamodule.val_split_mode.value),
        split_images=len(validation),
        split_images_in_test=len(validation & test),
        tuned_on_test=bool(validation & test),
    )


def _model_spec(
    model: HostBufferedPatchcore, *, seed: int, train_batch_size: int, eval_batch_size: int
) -> ModelSpec:
    """Describe the model from the model itself."""
    backbone = model.model.feature_extractor.feature_extractor
    weights = cast("dict[str, Any]", backbone.pretrained_cfg)
    parameter = next(model.model.parameters())
    return ModelSpec(
        name=MODEL_NAME,
        variant=type(model).__name__,
        backbone=model.model.backbone,
        weights=str(weights.get("hf_hub_id") or weights.get("tag") or "unknown"),
        layers=tuple(model.model.layers),
        image_size=IMAGE_SIZE,
        coreset_sampling_ratio=model.coreset_sampling_ratio,
        num_neighbors=model.model.num_neighbors,
        precision=str(parameter.dtype).removeprefix("torch."),
        seed=seed,
        train_batch_size=train_batch_size,
        eval_batch_size=eval_batch_size,
    )


def train_category(
    category: str,
    *,
    visa_dir: Path,
    models_dir: Path,
    seed: int = DEFAULT_SEED,
    backbone: str = DEFAULT_BACKBONE,
    train_batch_size: int = 32,
    eval_batch_size: int = 32,
    num_workers: int = 8,
) -> TrainRecord:
    """Train PatchCore on one category's normal images and evaluate it on the test split.

    Writes the split if it is not there, fits through Anomalib's Engine
    (features, coreset, thresholds on the validation split), runs Anomalib's
    test pass, and leaves the checkpoint with its record under
    `model_dir(models_dir, category)`, replacing any previous model whole.

    Args:
        category: The category to train, such as "pcb4".
        visa_dir: The dataset directory `data fetch` wrote.
        models_dir: The root for trained models.
        seed: The seed for the coreset's random projection and first pick.
        backbone: The feature extractor, as timm names it. The product's is
            Anomalib's default; another is for comparison only and belongs
            under its own `models_dir`.
        train_batch_size: Images per training batch.
        eval_batch_size: Images per validation and test batch.
        num_workers: Data loader workers.

    Returns:
        The training record, as written to `train.json`.

    Raises:
        RuntimeError: If CUDA is not available.
        SplitError: If the split cannot be written from the fetched tree.
    """
    device = cuda_device()
    split = write_split(visa_dir, [category])[category]
    seed_everything(seed, workers=True)
    datamodule = Visa(
        root=visa_dir,
        category=category,
        train_batch_size=train_batch_size,
        eval_batch_size=eval_batch_size,
        num_workers=num_workers,
        seed=seed,
    )
    model = HostBufferedPatchcore(
        backbone=backbone,
        pre_processor=HostBufferedPatchcore.configure_pre_processor(image_size=IMAGE_SIZE),
        visualizer=False,
    )
    clock = _PhaseClock()

    with (
        atomic_directory(model_dir(models_dir, category)) as partial,
        tempfile.TemporaryDirectory(prefix=f".{category}.engine.", dir=partial.parent) as work,
        _quiet_lightning(),
    ):
        engine = Engine(
            default_root_dir=work,
            accelerator="gpu",
            devices=1,
            callbacks=[
                ModelCheckpoint(dirpath=partial, filename=Path(CHECKPOINT_NAME).stem),
                clock,
            ],
            enable_model_summary=False,
        )
        gpu_free_bytes, _ = torch.cuda.mem_get_info(device.index)
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        engine.fit(model=model, datamodule=datamodule)
        fit_seconds = time.perf_counter() - started

        clock.mark("fit")
        results = engine.test(model=model, datamodule=datamodule)
        clock.mark("test")

        embed = clock.phase("embed", "start")
        coreset = clock.phase("coreset", "embed")
        validate = clock.phase("validate", "coreset")
        test = clock.phase("test", "fit")
        phases = (embed, coreset, validate, test)
        checkpoint = partial / CHECKPOINT_NAME
        bank_rows, bank_dims = model.model.memory_bank.shape
        record = TrainRecord(
            category=category,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            model=_model_spec(
                model, seed=seed, train_batch_size=train_batch_size, eval_batch_size=eval_batch_size
            ),
            train_images=split.train_good,
            test_good=split.test_good,
            test_bad=split.test_bad,
            embedding_rows=model.embedding_rows,
            memory_bank_rows=bank_rows,
            memory_bank_dims=bank_dims,
            thresholds=_thresholds(model, datamodule),
            metrics=Metrics(
                image_auroc=results[0]["image_AUROC"],
                pixel_auroc=results[0]["pixel_AUROC"],
                image_f1=results[0]["image_F1Score"],
                pixel_f1=results[0]["pixel_F1Score"],
            ),
            embed=embed,
            coreset=coreset,
            validate_split=validate,
            test=test,
            fit_seconds=fit_seconds,
            peak_allocated_bytes=max(phase.peak_allocated_bytes for phase in phases),
            peak_reserved_bytes=max(phase.peak_reserved_bytes for phase in phases),
            gpu_free_bytes_before=gpu_free_bytes,
            device=device,
            checkpoint=CHECKPOINT_NAME,
            checkpoint_bytes=checkpoint.stat().st_size,
            versions={name: version(name) for name in VERSIONED},
        )
        (partial / TRAIN_RECORD_NAME).write_text(
            record.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return record
