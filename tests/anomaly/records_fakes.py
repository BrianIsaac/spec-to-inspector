"""Records with plausible values, for tests that need one without training."""

from spec_to_inspector.anomaly.records import (
    InferenceOptions,
    Metrics,
    ModelSpec,
    Phase,
    RunIndex,
    Thresholds,
    TrainRecord,
)
from spec_to_inspector.device import CudaDevice

GIB = 1024**3


def thresholds() -> Thresholds:
    """Thresholds chosen on a 201-image test split.

    Returns:
        The thresholds.
    """
    return Thresholds(
        image=29.8,
        pixel=30.7,
        image_min=22.3,
        image_max=54.5,
        pixel_min=11.6,
        pixel_max=52.8,
        method="anomalib.metrics.F1AdaptiveThreshold",
        val_split_mode="same_as_test",
        split_images=201,
        split_images_in_test=201,
        tuned_on_test=True,
    )


def device() -> CudaDevice:
    """The laptop's GPU.

    Returns:
        The device.
    """
    return CudaDevice(
        index=0,
        name="NVIDIA GeForce RTX 5070 Ti Laptop GPU",
        capability=(12, 0),
        total_memory_bytes=12_344_164_352,
        torch_version="2.14.1+cu130",
        cuda_version="13.0",
        arch_list=("sm_100", "sm_120"),
    )


def train_record(category: str, *, image_auroc: float = 0.986, seed: int = 0) -> TrainRecord:
    """A training record for a category.

    Args:
        category: The category's name.
        image_auroc: The image AUROC to carry.
        seed: The seed to carry.

    Returns:
        The record.
    """
    return TrainRecord(
        category=category,
        created_at="2026-10-10T12:00:00+00:00",
        model=ModelSpec(
            name="patchcore",
            variant="HostBufferedPatchcore",
            backbone="wide_resnet50_2",
            weights="timm/wide_resnet50_2.racm_in1k",
            layers=("layer2", "layer3"),
            image_size=(256, 256),
            coreset_sampling_ratio=0.1,
            num_neighbors=9,
            precision="float32",
            seed=seed,
            train_batch_size=32,
            eval_batch_size=32,
        ),
        train_images=904,
        test_good=101,
        test_bad=100,
        embedding_rows=925_696,
        memory_bank_rows=92_569,
        memory_bank_dims=1536,
        thresholds=thresholds(),
        metrics=Metrics(image_auroc=image_auroc, pixel_auroc=0.984, image_f1=0.946, pixel_f1=0.427),
        embed=Phase(seconds=20.0, peak_allocated_bytes=GIB, peak_reserved_bytes=2 * GIB),
        coreset=Phase(seconds=720.0, peak_allocated_bytes=8 * GIB, peak_reserved_bytes=9 * GIB),
        validate_split=Phase(
            seconds=12.0, peak_allocated_bytes=2 * GIB, peak_reserved_bytes=3 * GIB
        ),
        test=Phase(seconds=13.0, peak_allocated_bytes=2 * GIB, peak_reserved_bytes=3 * GIB),
        fit_seconds=761.0,
        peak_allocated_bytes=8 * GIB,
        peak_reserved_bytes=9 * GIB,
        gpu_free_bytes_before=11 * GIB,
        device=device(),
        checkpoint="model.ckpt",
        checkpoint_bytes=668_470_503,
        versions={"anomalib": "2.7.0", "torch": "2.14.1+cu130"},
    )


def run_index(category: str, *, images: int = 201, image_auroc: float | None = 0.986) -> RunIndex:
    """A run index for a category, without entries.

    Args:
        category: The category's name.
        images: Images in the run.
        image_auroc: The run's image AUROC.

    Returns:
        The index.
    """
    return RunIndex(
        category=category,
        created_at="2026-10-10T12:20:00+00:00",
        thresholds=thresholds(),
        options=InferenceOptions(),
        images=images,
        labelled_good=images // 2,
        labelled_bad=images - images // 2,
        image_auroc=image_auroc,
        seconds=30.0,
        entries=[],
    )
