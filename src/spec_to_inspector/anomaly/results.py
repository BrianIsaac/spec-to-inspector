"""The anomaly model's measured figures, collected into one tracked file.

`models/` and `runs/` are outside git and go with the worktree; this module
reads each category's training record, run index and bench record from them
and writes `results/stage1/anomaly.json`, the file the deck's figures and the
later units quote.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.infer import load_run_index, run_dir
from spec_to_inspector.anomaly.records import (
    SCHEMA_VERSION,
    InferenceBench,
    InferenceOptions,
    RunIndex,
    TrainRecord,
)
from spec_to_inspector.anomaly.reference import (
    GATE_POINTS,
    REFERENCE_BACKBONE,
    REFERENCE_NOTE,
    REFERENCE_SOURCE,
    Comparison,
    compare,
)
from spec_to_inspector.anomaly.throughput import load_bench
from spec_to_inspector.anomaly.train import load_train_record

UNIT: Final = "U2"
NOTES: Final = (
    "AUROC and F1 are fractions of 1; *_points are percentage points (AUROC x 100).",
    "*_bytes are bytes; *_seconds and seconds are wall-clock seconds.",
    "Thresholds, scores and anomaly-map values are raw PatchCore distances, not normalised.",
    "peak_allocated_bytes is torch.cuda.max_memory_allocated; peak_reserved_bytes is "
    "torch.cuda.max_memory_reserved, which is what the card actually gives up.",
    "Where thresholds.tuned_on_test is true, every thresholded figure (F1, the confusion "
    "counts, predicted_anomalous) was tuned on the test images; AUROC needs no threshold.",
)


class RunSummary(BaseModel):
    """A category's test-split run, without its per-image lines.

    The confusion counts apply the image threshold to the labelled images.

    Attributes:
        directory: The run's directory, as it was when collected.
        created_at: When the run ended, in UTC, ISO 8601.
        options: How the images were scored and cropped.
        images: Images in the run.
        labelled_good: Images whose ground truth is "good".
        labelled_bad: Images whose ground truth is "bad".
        image_auroc: Area under the ROC curve of the run's own raw image scores.
        seconds: Wall time of the run, output files included.
        predicted_anomalous: Images scored above the image threshold.
        true_positive: Anomalous images scored above the threshold.
        false_negative: Anomalous images scored at or under it.
        true_negative: Normal images scored at or under the threshold.
        false_positive: Normal images scored above it.
        regions: Regions found across the run.
        images_with_regions: Images with at least one region.
        flagged_without_region: Images scored above the threshold that have no region.
        peak_fallback_images: Images whose one region is the peak-patch fallback.
        anomalous_with_region: Anomalous images with at least one region.
        anomalous_top_region_on_defect: Anomalous images whose region 1 touches
            the ground-truth mask.
    """

    model_config = ConfigDict(frozen=True)

    directory: str
    created_at: str
    options: InferenceOptions
    images: int
    labelled_good: int
    labelled_bad: int
    image_auroc: float | None
    seconds: float
    predicted_anomalous: int
    true_positive: int
    false_negative: int
    true_negative: int
    false_positive: int
    regions: int
    images_with_regions: int
    flagged_without_region: int
    peak_fallback_images: int
    anomalous_with_region: int
    anomalous_top_region_on_defect: int


class CategoryFigures(BaseModel):
    """Everything measured for one category.

    Attributes:
        category: The category's name.
        comparison: The image AUROC beside its published reference, where one exists.
        record: The training record, whole.
        run: The test-split run's summary; None if the split was not scored.
        bench: Throughput and inference memory; None if not benchmarked.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    comparison: Comparison | None
    record: TrainRecord
    run: RunSummary | None
    bench: InferenceBench | None


class AnomalyResults(BaseModel):
    """The tracked file of the anomaly model's figures.

    Attributes:
        schema_version: The version of this file's layout.
        unit: The Stage I unit that measured the figures.
        created_at: When the file was collected, in UTC, ISO 8601.
        written_by: The command line that collected it.
        reference_source: Where the published figures come from.
        reference_backbone: The backbone the published figures were measured with.
        reference_note: How the published setting differs from the one measured here.
        gate_points: How many points under its reference a category may be.
        outside_gate: The categories more than that under, if any.
        thresholds_tuned_on_test: Whether any category's thresholds were chosen
            on test images.
        notes: The units and conventions of the figures.
        categories: The figures per category.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    unit: str = UNIT
    created_at: str
    written_by: list[str]
    reference_source: str = REFERENCE_SOURCE
    reference_backbone: str = REFERENCE_BACKBONE
    reference_note: str = REFERENCE_NOTE
    gate_points: float = GATE_POINTS
    outside_gate: list[str]
    thresholds_tuned_on_test: bool
    notes: list[str] = list(NOTES)
    categories: dict[str, CategoryFigures]


def _summarise(index: RunIndex, directory: Path) -> RunSummary:
    """Reduce a run's index to its counts."""
    labelled = [(entry.label, entry.predicted_anomalous) for entry in index.entries]
    return RunSummary(
        directory=str(directory),
        created_at=index.created_at,
        options=index.options,
        images=index.images,
        labelled_good=index.labelled_good,
        labelled_bad=index.labelled_bad,
        image_auroc=index.image_auroc,
        seconds=index.seconds,
        predicted_anomalous=sum(entry.predicted_anomalous for entry in index.entries),
        true_positive=labelled.count(("bad", True)),
        false_negative=labelled.count(("bad", False)),
        true_negative=labelled.count(("good", False)),
        false_positive=labelled.count(("good", True)),
        regions=sum(entry.regions for entry in index.entries),
        images_with_regions=sum(entry.regions > 0 for entry in index.entries),
        flagged_without_region=sum(
            entry.predicted_anomalous and entry.regions == 0 for entry in index.entries
        ),
        peak_fallback_images=sum(entry.peak_fallback for entry in index.entries),
        anomalous_with_region=sum(
            entry.label == "bad" and entry.regions > 0 for entry in index.entries
        ),
        anomalous_top_region_on_defect=sum(
            entry.label == "bad" and entry.top_region_on_ground_truth is True
            for entry in index.entries
        ),
    )


def collect(
    categories: Sequence[str], *, models_dir: Path, runs_dir: Path, written_by: Sequence[str]
) -> AnomalyResults:
    """Gather the categories' figures from their records on disk.

    Args:
        categories: The categories to report, in order.
        models_dir: The root for trained models.
        runs_dir: The root for run outputs.
        written_by: The command line collecting the figures, for the record.

    Returns:
        The results, ready to write.

    Raises:
        ModelNotTrainedError: If a category has no model on disk.
    """
    figures: dict[str, CategoryFigures] = {}
    for category in categories:
        record = load_train_record(models_dir, category)
        directory = run_dir(runs_dir, category)
        run = _summarise(load_run_index(directory), directory) if directory.is_dir() else None
        figures[category] = CategoryFigures(
            category=category,
            comparison=compare(category, record.metrics.image_auroc),
            record=record,
            run=run,
            bench=load_bench(runs_dir / category),
        )
    return AnomalyResults(
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        written_by=list(written_by),
        outside_gate=[
            category
            for category, entry in figures.items()
            if entry.comparison is not None and not entry.comparison.within_gate
        ],
        thresholds_tuned_on_test=any(
            entry.record.thresholds.tuned_on_test for entry in figures.values()
        ),
        categories=figures,
    )


def write_results(path: Path, results: AnomalyResults) -> None:
    """Write the results as indented JSON.

    Args:
        path: The file to write, such as `results/stage1/anomaly.json`.
        results: The results.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(results.model_dump_json(indent=2) + "\n", encoding="utf-8")
