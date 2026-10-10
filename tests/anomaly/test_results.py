"""Tests for collecting the measured figures into the tracked results file."""

import json
from pathlib import Path

import pytest

from spec_to_inspector.anomaly.infer import RUN_INDEX_NAME, run_dir
from spec_to_inspector.anomaly.records import InferenceBench, RunEntry, Throughput
from spec_to_inspector.anomaly.results import AnomalyResults, collect, write_results
from spec_to_inspector.anomaly.throughput import BENCH_NAME
from spec_to_inspector.anomaly.train import (
    CHECKPOINT_NAME,
    TRAIN_RECORD_NAME,
    ModelNotTrainedError,
    model_dir,
)
from tests.anomaly.records_fakes import device, run_index, train_record


def _put_model(models: Path, category: str, image_auroc: float) -> None:
    base = model_dir(models, category)
    base.mkdir(parents=True)
    (base / CHECKPOINT_NAME).write_bytes(b"weights")
    (base / TRAIN_RECORD_NAME).write_text(
        train_record(category, image_auroc=image_auroc).model_dump_json()
    )


def _entry(
    image_id: str,
    score: float,
    *,
    flagged: bool,
    regions: int,
    fallback: bool = False,
    on_defect: bool | None = None,
) -> RunEntry:
    return RunEntry(
        image_id=image_id,
        result=f"{image_id}/result.json",
        label="bad" if image_id.startswith("bad") else "good",
        score=score,
        predicted_anomalous=flagged,
        regions=regions,
        peak_fallback=fallback,
        top_region_on_ground_truth=on_defect,
    )


def _put_run(runs: Path, category: str) -> None:
    entries = [
        _entry("good-0", 20.0, flagged=False, regions=0),
        _entry("good-1", 31.0, flagged=True, regions=2),
        _entry("bad-0", 45.0, flagged=True, regions=3, on_defect=True),
        _entry("bad-1", 25.0, flagged=False, regions=1, on_defect=False),
        _entry("bad-2", 50.0, flagged=True, regions=1, fallback=True, on_defect=True),
    ]
    index = run_index(category, images=5).model_copy(
        update={"entries": entries, "labelled_good": 2, "labelled_bad": 3}
    )
    directory = run_dir(runs, category)
    directory.mkdir(parents=True)
    (directory / RUN_INDEX_NAME).write_text(index.model_dump_json())


def _put_bench(runs: Path, category: str) -> InferenceBench:
    bench = InferenceBench(
        category=category,
        created_at="2026-10-10T13:00:00+00:00",
        device=device(),
        images=201,
        resident_bytes=800_000_000,
        runs=[
            Throughput(
                mode="model",
                batch_size=1,
                images=201,
                pass_seconds=[2.0, 2.1, 1.9],
                seconds=2.0,
                images_per_second=100.5,
                peak_allocated_bytes=10**9,
                peak_reserved_bytes=2 * 10**9,
                num_workers=None,
            )
        ],
    )
    (runs / category).mkdir(parents=True, exist_ok=True)
    (runs / category / BENCH_NAME).write_text(bench.model_dump_json())
    return bench


def test_the_results_carry_each_categorys_record_and_its_comparison(tmp_path: Path) -> None:
    """A category's figures are its training record whole, beside the published reference."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_model(models, "pcb3", 0.90)

    results = collect(["pcb3", "pcb4"], models_dir=models, runs_dir=runs, written_by=["train"])

    assert list(results.categories) == ["pcb3", "pcb4"]
    pcb4 = results.categories["pcb4"]
    assert pcb4.record == train_record("pcb4", image_auroc=0.9857)
    assert pcb4.comparison is not None
    assert pcb4.comparison.delta_points == -0.43
    assert pcb4.comparison.within_gate
    assert pcb4.run is None
    assert pcb4.bench is None
    assert not results.categories["pcb3"].comparison.within_gate  # pyright: ignore[reportOptionalMemberAccess]
    assert results.outside_gate == ["pcb3"]
    assert results.unit == "U2"
    assert results.written_by == ["train"]
    assert results.gate_points == 3.0
    assert "Rolih" in results.reference_source
    assert results.reference_backbone == "resnet18"
    assert "like for like" in results.reference_note
    assert results.thresholds_tuned_on_test is True


def test_a_run_is_summarised_without_its_per_image_lines(tmp_path: Path) -> None:
    """The run's counts and confusion at the image threshold are kept; its entries are not."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_run(runs, "pcb4")

    run = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=[]).categories["pcb4"].run

    assert run is not None
    assert run.images == 5
    assert run.image_auroc == 0.986
    assert run.predicted_anomalous == 3
    assert (run.true_positive, run.false_negative) == (2, 1)
    assert (run.true_negative, run.false_positive) == (1, 1)
    assert run.regions == 7
    assert run.images_with_regions == 4
    assert run.flagged_without_region == 0
    assert run.peak_fallback_images == 1
    assert run.anomalous_with_region == 3
    assert run.anomalous_top_region_on_defect == 2
    assert run.directory == str(run_dir(runs, "pcb4"))
    assert "entries" not in run.model_dump()


def test_a_bench_is_included_when_there_is_one(tmp_path: Path) -> None:
    """Throughput and inference memory ride along once a category has been benchmarked."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    bench = _put_bench(runs, "pcb4")

    results = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=[])

    assert results.categories["pcb4"].bench == bench


def test_an_untrained_category_cannot_be_reported(tmp_path: Path) -> None:
    """Figures are never written for a category with no model on disk."""
    with pytest.raises(ModelNotTrainedError, match="pcb4"):
        collect(["pcb4"], models_dir=tmp_path / "models", runs_dir=tmp_path / "runs", written_by=[])


def test_the_results_file_is_stable_json(tmp_path: Path) -> None:
    """The file is indented JSON ending in a newline, and reads back as the same results."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_run(runs, "pcb4")
    results = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=["train", "--all"])
    path = tmp_path / "results" / "stage1" / "anomaly.json"

    write_results(path, results)

    text = path.read_text()
    assert text.endswith("}\n")
    assert json.loads(text)["categories"]["pcb4"]["record"]["metrics"]["image_auroc"] == 0.9857
    assert AnomalyResults.model_validate_json(text) == results
    assert any("fraction" in note for note in results.notes)


def test_a_run_made_with_another_model_is_left_out_and_named(tmp_path: Path) -> None:
    """A run whose thresholds are not the model's, or that predates it, is not reported."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_run(runs, "pcb4")
    _put_bench(runs, "pcb4")
    base = model_dir(models, "pcb4")
    retrained = train_record("pcb4", image_auroc=0.9857).model_copy(
        update={"created_at": "2026-10-10T14:00:00+00:00"}
    )
    (base / TRAIN_RECORD_NAME).write_text(retrained.model_dump_json())

    figures = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=[]).categories["pcb4"]

    assert figures.run is None
    assert figures.bench is None
    assert figures.stale == ["run", "bench"]


def test_a_run_with_other_thresholds_is_stale_whatever_its_date(tmp_path: Path) -> None:
    """Thresholds that differ from the model's mean the run scored with another model."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_run(runs, "pcb4")
    base = model_dir(models, "pcb4")
    record = train_record("pcb4", image_auroc=0.9857)
    other = record.thresholds.model_copy(update={"image": 12.5})
    (base / TRAIN_RECORD_NAME).write_text(
        record.model_copy(update={"thresholds": other}).model_dump_json()
    )

    figures = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=[]).categories["pcb4"]

    assert figures.run is None
    assert figures.stale == ["run"]


def test_fresh_records_are_not_stale(tmp_path: Path) -> None:
    """A run and a bench made after the model, with its thresholds, are reported."""
    models, runs = tmp_path / "models", tmp_path / "runs"
    _put_model(models, "pcb4", 0.9857)
    _put_run(runs, "pcb4")
    _put_bench(runs, "pcb4")

    figures = collect(["pcb4"], models_dir=models, runs_dir=runs, written_by=[]).categories["pcb4"]

    assert figures.run is not None
    assert figures.bench is not None
    assert figures.stale == []
