"""Tests for the per-category orchestration behind `spec-to-inspector train`, without a GPU."""

from pathlib import Path

import pytest

from spec_to_inspector.anomaly import pipeline
from spec_to_inspector.anomaly.records import (
    InferenceBench,
    InferenceOptions,
    RunIndex,
    TrainRecord,
)
from spec_to_inspector.device import CudaDevice
from tests.anomaly.records_fakes import device, inference_bench, run_index, train_record


class _Calls:
    """Stands in for training, loading and inference, recording what was asked."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.trained: list[str] = []
        self.loaded: list[str] = []
        self.runs: list[tuple[str, Path, int]] = []
        self.backbones: list[str] = []
        self.benched: list[tuple[str, Path, int]] = []

    def train_category(
        self, category: str, *, visa_dir: Path, models_dir: Path, seed: int, backbone: str
    ) -> TrainRecord:
        self.trained.append(category)
        self.backbones.append(backbone)
        assert visa_dir.name == "visa"
        assert models_dir == self.models_dir
        return train_record(category, seed=seed)

    def measure(
        self, model: str, items: list[str], category_dir: Path, *, device: CudaDevice
    ) -> InferenceBench:
        self.benched.append((model, category_dir, len(items)))
        return inference_bench(model)

    def load_train_record(self, models_dir: Path, category: str) -> TrainRecord:
        if category == "pcb2":
            return train_record(category, image_auroc=0.5)
        raise pipeline.ModelNotTrainedError(category)

    def load_model(self, models_dir: Path, category: str) -> str:
        self.loaded.append(category)
        return category

    def visa_test_items(self, visa_dir: Path, category: str) -> list[str]:
        return [f"{category}-a", f"{category}-b"]

    def run_inference(
        self, model: str, items: list[str], output_dir: Path, *, options: InferenceOptions
    ) -> RunIndex:
        self.runs.append((model, output_dir, options.batch_size))
        return run_index(model, images=len(items))


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Calls:
    """Replace the GPU work with recorders.

    Returns:
        The recorder.
    """
    recorder = _Calls(tmp_path / "models")
    monkeypatch.setattr(pipeline, "train_category", recorder.train_category)
    monkeypatch.setattr(pipeline, "load_train_record", recorder.load_train_record)
    monkeypatch.setattr(pipeline.AnomalyModel, "load", recorder.load_model)
    monkeypatch.setattr(pipeline, "visa_test_items", recorder.visa_test_items)
    monkeypatch.setattr(pipeline, "run_inference", recorder.run_inference)
    monkeypatch.setattr(pipeline, "measure", recorder.measure)
    monkeypatch.setattr(pipeline, "cuda_device", device)
    return recorder


def _run(
    tmp_path: Path,
    category: str,
    *,
    reuse: bool = False,
    infer: bool = True,
    bench: bool = False,
    seed: int = 0,
    backbone: str = "wide_resnet50_2",
    options: InferenceOptions | None = None,
) -> pipeline.CategoryOutcome:
    return pipeline.train_and_score(
        category,
        visa_dir=tmp_path / "data" / "visa",
        models_dir=tmp_path / "models",
        runs_dir=tmp_path / "runs",
        reuse=reuse,
        infer=infer,
        bench=bench,
        seed=seed,
        backbone=backbone,
        options=options,
    )


def test_a_category_is_trained_then_its_test_split_is_scored(calls: _Calls, tmp_path: Path) -> None:
    """By default a category is trained, loaded, and run over its test split."""
    outcome = _run(tmp_path, "pcb4", seed=5)

    assert calls.trained == ["pcb4"]
    assert calls.loaded == ["pcb4"]
    assert calls.runs == [("pcb4", tmp_path / "runs" / "pcb4" / "test", 16)]
    assert outcome.trained
    assert outcome.record.model.seed == 5
    assert outcome.run is not None
    assert outcome.run.images == 2
    assert outcome.run_dir == tmp_path / "runs" / "pcb4" / "test"


def test_inference_can_be_left_out(calls: _Calls, tmp_path: Path) -> None:
    """Without inference nothing is loaded or written under the runs directory."""
    outcome = _run(tmp_path, "pcb4", infer=False)

    assert calls.trained == ["pcb4"]
    assert calls.loaded == []
    assert outcome.run is None
    assert outcome.run_dir is None


def test_reuse_keeps_a_model_that_is_on_disk(calls: _Calls, tmp_path: Path) -> None:
    """With reuse, a category already trained is not trained again, only scored."""
    outcome = _run(tmp_path, "pcb2", reuse=True)

    assert calls.trained == []
    assert calls.loaded == ["pcb2"]
    assert not outcome.trained
    assert outcome.record.metrics.image_auroc == 0.5


def test_reuse_trains_a_category_that_is_missing(calls: _Calls, tmp_path: Path) -> None:
    """With reuse, a category with no model on disk is trained as usual."""
    outcome = _run(tmp_path, "pcb4", reuse=True)

    assert calls.trained == ["pcb4"]
    assert outcome.trained


def test_inference_options_reach_the_run(calls: _Calls, tmp_path: Path) -> None:
    """The caller's inference options are the run's."""
    _run(tmp_path, "pcb4", options=InferenceOptions(batch_size=4))

    assert calls.runs[0][2] == 4


def test_a_bench_is_measured_on_the_test_split_when_asked(calls: _Calls, tmp_path: Path) -> None:
    """With bench, throughput is measured on the test split into the category's runs directory."""
    outcome = _run(tmp_path, "pcb4", bench=True)

    assert calls.benched == [("pcb4", tmp_path / "runs" / "pcb4", 2)]
    assert calls.loaded == ["pcb4"]
    assert outcome.bench == inference_bench("pcb4")
    assert _run(tmp_path, "pcb4").bench is None


def test_a_bench_does_not_need_the_run(calls: _Calls, tmp_path: Path) -> None:
    """Throughput can be measured without writing the test split's outputs."""
    outcome = _run(tmp_path, "pcb4", infer=False, bench=True)

    assert calls.runs == []
    assert calls.benched == [("pcb4", tmp_path / "runs" / "pcb4", 2)]
    assert outcome.run is None
    assert outcome.bench is not None


def test_the_backbone_reaches_training(calls: _Calls, tmp_path: Path) -> None:
    """The backbone asked for is the one trained; the default is Anomalib's."""
    _run(tmp_path, "pcb4")
    _run(tmp_path, "pcb4", backbone="resnet18")

    assert calls.backbones == ["wide_resnet50_2", "resnet18"]
