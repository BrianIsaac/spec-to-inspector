"""Tests for the OpenVINO scorer, with a stand-in for the compiled graph."""

from pathlib import Path

import numpy as np
import pytest
import torch
from numpy.typing import NDArray
from PIL import Image
from torchvision.transforms.v2 import Compose, Resize

from spec_to_inspector.anomaly.infer import AnomalyModel, InferenceItem, run_inference
from spec_to_inspector.anomaly.model import SingleCopyPatchcore
from spec_to_inspector.anomaly.ov_model import (
    OpenVinoModel,
    export_openvino,
    ir_path,
)
from spec_to_inspector.anomaly.throughput import measure, measure_model
from spec_to_inspector.anomaly.train import IMAGE_SIZE, TRAIN_RECORD_NAME, model_dir, train_category
from tests.anomaly.fakes import write_trainable_visa
from tests.anomaly.records_fakes import device, train_record


class _Graph:
    """Stands in for a compiled graph fixed at one batch: scores an image by its first pixel."""

    def __init__(self, batch_size: int) -> None:
        self.batch_size = batch_size
        self.batches: list[NDArray[np.float32]] = []

    def __call__(
        self, batch: NDArray[np.float32]
    ) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        assert batch.shape[0] == self.batch_size, "a graph takes only its own batch size"
        self.batches.append(batch)
        first_pixels = batch[:, 0, 0, 0]
        maps = np.broadcast_to(first_pixels[:, None, None, None], (batch.shape[0], 1, 256, 256))
        return first_pixels.copy(), maps.copy()


def _model(batch_size: int) -> tuple[OpenVinoModel, _Graph]:
    graph = _Graph(batch_size)
    return (
        OpenVinoModel(graph, train_record("pcb4"), batch_size=batch_size, resident_bytes=668),
        graph,
    )


def _images(count: int) -> torch.Tensor:
    images = torch.zeros(count, 3, 256, 256)
    for index in range(count):
        images[index, 0, 0, 0] = index + 1
    return images


def test_a_full_batch_goes_through_once() -> None:
    """Scores and maps come back in the scorer's shapes, in host memory."""
    model, graph = _model(4)
    scores, maps = model.score(_images(4))

    assert len(graph.batches) == 1
    assert scores.tolist() == [1, 2, 3, 4]
    assert maps.shape == (4, 256, 256)
    assert maps[2, 10, 10] == 3


def test_a_short_batch_is_filled_out_and_the_fillers_answers_dropped() -> None:
    """A graph fixed at 16 still answers for the last 8 images of a set."""
    model, graph = _model(4)
    scores, maps = model.score(_images(3))

    assert graph.batches[0].shape[0] == 4
    assert graph.batches[0][:, 0, 0, 0].tolist() == [1, 2, 3, 3]
    assert scores.tolist() == [1, 2, 3]
    assert maps.shape == (3, 256, 256)


def test_a_long_batch_is_cut_to_the_graphs_size_in_order() -> None:
    """Whatever the caller's batch, the answers come back in its order."""
    model, graph = _model(2)
    scores, _ = model.score(_images(5))

    assert [batch.shape[0] for batch in graph.batches] == [2, 2, 2]
    assert scores.tolist() == [1, 2, 3, 4, 5]


def test_the_model_answers_as_the_runs_and_the_bench_ask(tmp_path: Path) -> None:
    """The same `run_inference` and `measure` as PyTorch's take it, with nothing changed in them."""
    model, _ = _model(16)
    folder = tmp_path / "images"
    folder.mkdir()
    items: list[InferenceItem] = []
    for index in range(3):
        path = folder / f"{index}.png"
        Image.fromarray(np.full((64, 64, 3), index * 40, dtype=np.uint8)).save(path)
        items.append(InferenceItem(image_id=f"good-{index}", path=path, label="good"))

    run = run_inference(model, items, tmp_path / "run")
    bench = measure(
        model, items, tmp_path / "bench", device=device(), batch_sizes=(16,), num_workers=0
    )

    assert run.images == 3
    assert run.thresholds == train_record("pcb4").thresholds
    assert {throughput.batch_size for throughput in bench.runs} == {16}
    assert bench.resident_bytes == 668
    assert all(throughput.peak_allocated_bytes == 0 for throughput in bench.runs)


def test_a_timed_pass_counts_the_images_and_not_the_filler() -> None:
    """Images a second are the set's, for all that a short batch computes a whole one."""
    model, graph = _model(4)
    throughput = measure_model(model, _images(6), batch_size=4, repeats=1, warmup_batches=0)

    assert throughput.images == 6
    assert sum(batch.shape[0] for batch in graph.batches[:2]) == 8


def test_the_first_use_runs_one_whole_batch_on_nothing() -> None:
    """It reports a time and leaves no state behind."""
    model, graph = _model(4)
    assert model.first_use() >= 0
    assert graph.batches[0].shape == (4, 3, *IMAGE_SIZE)
    assert graph.batches[0].max() == 0


def test_the_resize_is_the_models_own() -> None:
    """The graph holds the model's transform; the data loader's resize has to be the same one."""
    model, _ = _model(1)
    transform = SingleCopyPatchcore.configure_pre_processor(image_size=IMAGE_SIZE).transform
    assert isinstance(transform, Compose)
    theirs = transform.transforms[0]
    ours = model.resize

    assert isinstance(theirs, Resize)
    assert isinstance(ours, Resize)
    assert (ours.size, ours.antialias) == (theirs.size, theirs.antialias)


def test_the_map_cell_is_the_trained_models() -> None:
    """A patch covers the same pixels of the map here as under PyTorch."""
    model, _ = _model(1)
    assert model.map_cell == (8, 8)
    assert model.category == "pcb4"
    assert model.device == torch.device("cpu")


def test_each_batch_size_has_its_own_graph(tmp_path: Path) -> None:
    """Two batch sizes of one part cannot overwrite each other."""
    one, sixteen = ir_path(tmp_path, "pcb4", 1), ir_path(tmp_path, "pcb4", 16)
    assert one != sixteen
    assert one.is_relative_to(model_dir(tmp_path, "pcb4"))
    assert one.suffix == ".xml"


def test_on_the_laptop_openvino_not_being_installed_is_said_plainly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is only in the xpu group; a laptop that asks is told so, not given an import error."""

    def absent(_name: str) -> None:
        raise ModuleNotFoundError

    monkeypatch.setattr("spec_to_inspector.anomaly.ov_model.import_module", absent)
    base = model_dir(tmp_path, "pcb4")
    base.mkdir(parents=True)
    (base / "model.ckpt").write_bytes(b"")
    (base / TRAIN_RECORD_NAME).write_text(
        train_record("pcb4").model_dump_json(indent=2), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="xpu group"):
        OpenVinoModel.load(tmp_path, "pcb4", batch_size=1)


@pytest.mark.xpu
@pytest.mark.parametrize("batch_size", [1, 16])
def test_on_the_card_the_graph_agrees_with_pytorch_in_raw_units_and_in_fp32(
    tmp_path: Path, batch_size: int
) -> None:
    """A real 20-image model, exported and compiled on `GPU.0`: the raw scores are PyTorch's."""
    visa = tmp_path / "data" / "visa"
    models = tmp_path / "models"
    write_trainable_visa(visa)
    train_category("pcb1", visa_dir=visa, models_dir=models, num_workers=2, device="xpu")
    pytorch = AnomalyModel.load(models, "pcb1", device="xpu")

    export_openvino(models, "pcb1", batch_size=batch_size)
    model = OpenVinoModel.load(models, "pcb1", batch_size=batch_size)
    images = torch.rand(batch_size, 3, *IMAGE_SIZE)
    scores, maps = model.score(images)
    want_scores, want_maps = pytorch.score(images)

    assert "float32" in model.properties["precision"]
    assert "float16" in model.properties["plugin_default_precision"]
    assert scores.shape == want_scores.shape
    assert maps.shape == want_maps.shape
    assert torch.abs(scores - want_scores.cpu()).max() < 0.01
    assert torch.abs(maps - want_maps.cpu()).max() < 0.01
