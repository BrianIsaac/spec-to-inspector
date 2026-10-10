"""How `spec-to-inspector train` reports what it measured."""

from collections.abc import Sequence
from pathlib import Path

from rich import box
from rich.table import Table

from spec_to_inspector.anomaly.pipeline import CategoryOutcome
from spec_to_inspector.anomaly.reference import (
    GATE_POINTS,
    REFERENCE_NOTE,
    REFERENCE_SOURCE,
    compare,
)
from spec_to_inspector.anomaly.throughput import BENCH_NAME
from spec_to_inspector.anomaly.train import CHECKPOINT_NAME, TRAIN_RECORD_NAME, model_dir

AUROC_TOLERANCE = 1e-4
"""How far the run's own image AUROC may sit from Anomalib's before it is called out."""


def _duration(seconds: float) -> str:
    """Write a duration as minutes and seconds."""
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest:02d} s" if minutes else f"{rest} s"


def outcome_table(outcomes: Sequence[CategoryOutcome]) -> Table:
    """Lay out each category's AUROC against its reference, its thresholds and its cost.

    Args:
        outcomes: The categories' outcomes.

    Returns:
        A table with one row per category.
    """
    table = Table(title="PatchCore on VisA, 256 px (Anomalib)", box=box.SIMPLE_HEAD)
    table.add_column("Category")
    for column in (
        "Image\nAUROC",
        "Published",
        "Delta",
        "Gate",
        "Pixel\nAUROC",
        "Image\nthreshold",
        "Pixel\nthreshold",
        "Fit",
        "Peak GPU\nallocated",
    ):
        table.add_column(column, justify="right")
    for outcome in outcomes:
        record = outcome.record
        comparison = compare(outcome.category, record.metrics.image_auroc)
        table.add_row(
            outcome.category,
            f"{record.metrics.image_auroc * 100:.2f}",
            "n/a" if comparison is None else f"{comparison.reference_points:.1f}",
            "n/a" if comparison is None else f"{comparison.delta_points:+.2f}",
            "n/a" if comparison is None else "within" if comparison.within_gate else "outside",
            f"{record.metrics.pixel_auroc * 100:.2f}",
            f"{record.thresholds.image:.3f}",
            f"{record.thresholds.pixel:.3f}",
            _duration(record.fit_seconds) if outcome.trained else "reused",
            f"{record.peak_allocated_bytes / 1024**3:.2f} GiB",
        )
    return table


def outcome_lines(
    outcomes: Sequence[CategoryOutcome], models_dir: Path, runs_dir: Path
) -> list[str]:
    """Say in words what the table cannot: the gate, the thresholds' provenance, the files.

    Args:
        outcomes: The categories' outcomes.
        models_dir: The root for trained models, as the user gave it.
        runs_dir: The root for run outputs, as the user gave it.

    Returns:
        The lines to print under the table.
    """
    lines = [f"Published: {REFERENCE_SOURCE}.", REFERENCE_NOTE]
    for outcome in outcomes:
        comparison = compare(outcome.category, outcome.record.metrics.image_auroc)
        if comparison is not None and not comparison.within_gate:
            lines.append(
                f"{outcome.category} is more than {GATE_POINTS:g} points under its published "
                f"reference: {comparison.measured_points:.2f} against "
                f"{comparison.reference_points:.1f}."
            )
    for outcome in outcomes:
        thresholds = outcome.record.thresholds
        where = (
            "chosen on the test split"
            if thresholds.tuned_on_test
            else "chosen on a validation split held out of the test split"
        )
        lines.append(
            f"{outcome.category} thresholds: {thresholds.method}, {where} "
            f"({thresholds.split_images_in_test} of {thresholds.split_images} validation images "
            f"are test images; val_split_mode {thresholds.val_split_mode}). "
            + (
                "Thresholded figures are tuned there; AUROC needs no threshold."
                if thresholds.tuned_on_test
                else ""
            )
        )
    for outcome in outcomes:
        directory = model_dir(models_dir, outcome.category)
        lines.append(
            f"{outcome.category} model: {directory} ({CHECKPOINT_NAME}, {TRAIN_RECORD_NAME})"
            + ("" if outcome.run_dir is None else f"; test split outputs: {outcome.run_dir}")
        )
        bench = outcome.bench
        if bench is not None:
            speeds = "; ".join(
                f"{run.images_per_second:.1f} at batch {run.batch_size} "
                f"({'model only' if run.mode == 'model' else 'end to end from disk'}, "
                f"peak {run.peak_allocated_bytes / 1024**3:.2f} GiB)"
                for run in bench.runs
            )
            lines.append(
                f"{outcome.category} inference, images/s on {bench.images} test images: {speeds}. "
                f"Resident model: {bench.resident_bytes / 1024**3:.2f} GiB. "
                f"Record: {runs_dir / outcome.category / BENCH_NAME}"
            )
        run = outcome.run
        if (
            run is not None
            and run.image_auroc is not None
            and abs(run.image_auroc - outcome.record.metrics.image_auroc) > AUROC_TOLERANCE
        ):
            lines.append(
                f"{outcome.category}: the run's image AUROC {run.image_auroc * 100:.2f} differs "
                f"from Anomalib's test pass {outcome.record.metrics.image_auroc * 100:.2f}."
            )
    return lines
