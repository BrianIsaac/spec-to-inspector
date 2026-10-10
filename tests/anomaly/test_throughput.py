"""Tests for the throughput measurement, with a stub in place of the model."""

import time
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torchvision.transforms.v2 import Resize

from spec_to_inspector.anomaly.infer import InferenceItem
from spec_to_inspector.anomaly.records import InferenceBench, Throughput
from spec_to_inspector.anomaly.throughput import (
    BENCH_NAME,
    load_bench,
    measure,
    measure_end_to_end,
    measure_model,
)
from tests.anomaly.records_fakes import device, thresholds


class _SlowModel:
    """A scorer that takes a fixed time per batch, so throughput is known in advance."""

    category = "pcb4"
    thresholds = thresholds()
    resize = Resize((256, 256), antialias=True)
    device = torch.device("cpu")
    resident_bytes = 123

    def __init__(self, seconds_per_batch: float = 0.01) -> None:
        self.seconds_per_batch = seconds_per_batch
        self.batches: list[int] = []

    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        assert images.shape[1:] == (3, 256, 256)
        self.batches.append(images.shape[0])
        time.sleep(self.seconds_per_batch)
        return torch.zeros(images.shape[0]), torch.zeros(images.shape[0], 256, 256)


def _items(tmp_path: Path, count: int = 10) -> list[InferenceItem]:
    items: list[InferenceItem] = []
    for index in range(count):
        path = tmp_path / "source" / f"{index:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((60, 80, 3), index, dtype=np.uint8)).save(path)
        items.append(InferenceItem(image_id=f"i{index:03d}", path=path))
    return items


def test_the_model_figure_times_forward_passes_only() -> None:
    """Images per second is the image count over the median pass, warm-up left out."""
    model = _SlowModel(seconds_per_batch=0.02)
    images = torch.rand(10, 3, 256, 256)

    result = measure_model(model, images, batch_size=4, repeats=3, warmup_batches=2)

    assert model.batches == [4, 4] + [4, 4, 2] * 3
    assert result.mode == "model"
    assert result.batch_size == 4
    assert result.images == 10
    assert len(result.pass_seconds) == 3
    assert result.seconds == sorted(result.pass_seconds)[1]
    assert result.images_per_second == pytest.approx(10 / result.seconds)
    assert 0.06 <= result.seconds < 0.2
    assert result.num_workers is None


def test_batch_one_makes_one_pass_per_image() -> None:
    """At batch 1 every image is its own forward pass."""
    model = _SlowModel(seconds_per_batch=0.0)

    result = measure_model(
        model, torch.rand(5, 3, 256, 256), batch_size=1, repeats=1, warmup_batches=1
    )

    assert model.batches == [1] * 6
    assert result.images == 5


def test_the_end_to_end_figure_starts_from_the_files(tmp_path: Path) -> None:
    """End to end, the images are decoded and resized from disk on every pass."""
    model = _SlowModel(seconds_per_batch=0.0)

    result = measure_end_to_end(
        model, _items(tmp_path), batch_size=4, num_workers=0, repeats=2, warmup_batches=1
    )

    assert model.batches == [4] + [4, 4, 2] * 2
    assert result.mode == "end_to_end"
    assert result.images == 10
    assert result.num_workers == 0
    assert len(result.pass_seconds) == 2
    assert result.images_per_second == pytest.approx(10 / result.seconds)


def test_a_bench_covers_both_figures_at_each_batch_size(tmp_path: Path) -> None:
    """One bench measures model-only and end-to-end throughput at every batch size asked."""
    model = _SlowModel(seconds_per_batch=0.0)

    bench = measure(
        model,
        _items(tmp_path),
        tmp_path / "runs" / "pcb4",
        device=device(),
        batch_sizes=(1, 4),
        num_workers=0,
        repeats=1,
    )

    assert [(run.mode, run.batch_size) for run in bench.runs] == [
        ("model", 1),
        ("end_to_end", 1),
        ("model", 4),
        ("end_to_end", 4),
    ]
    assert bench.category == "pcb4"
    assert bench.images == 10
    assert bench.resident_bytes == 123
    assert bench.device == device()
    assert (tmp_path / "runs" / "pcb4" / BENCH_NAME).is_file()
    assert load_bench(tmp_path / "runs" / "pcb4") == bench
    assert (
        InferenceBench.model_validate_json((tmp_path / "runs" / "pcb4" / BENCH_NAME).read_text())
        == bench
    )


def test_a_missing_bench_is_none(tmp_path: Path) -> None:
    """A category that was never benchmarked has no bench, not an error."""
    assert load_bench(tmp_path / "runs" / "pcb4") is None


def test_throughput_needs_an_image() -> None:
    """Measuring nothing is refused."""
    with pytest.raises(ValueError, match="no images"):
        measure_model(_SlowModel(), torch.empty(0, 3, 256, 256), batch_size=1)
    assert Throughput.model_fields["pass_seconds"].is_required()
