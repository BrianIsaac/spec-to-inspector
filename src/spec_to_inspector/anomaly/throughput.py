"""How fast a trained model scores images, and how much GPU memory it holds while it does.

Two figures per batch size, because they answer different questions:

- "model": the forward pass alone, on resized images already on the GPU. This
  is the card's own speed, the figure that moves when the card changes. Its
  peak memory is taken on a separate pass with one batch on the card at a
  time, so it is what inference holds and not the preloaded test set.
- "end_to_end": from the image files to scores and maps in host memory, with
  decoding and resizing in data loader workers. This is what a batch of
  boards costs; at these image sizes the CPU's JPEG decoding sets it.

Each is the median of a few passes over the category's test split, after a
warm-up, with the GPU synchronised before each clock reading.
"""

import statistics
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

import torch
from torch.utils.data import DataLoader

from spec_to_inspector.anomaly.infer import InferenceItem, Scorer, image_dataset
from spec_to_inspector.anomaly.records import InferenceBench, Throughput
from spec_to_inspector.device import CudaDevice

BENCH_NAME: Final = "bench.json"
BATCH_SIZES: Final = (1, 16)


class MeasurableScorer(Scorer, Protocol):
    """A scorer that also says where it lives and what it keeps there."""

    @property
    def device(self) -> torch.device:
        """Where the model lives."""
        ...

    @property
    def resident_bytes(self) -> int:
        """Bytes of the model's parameters and buffers on the device."""
        ...


def _synchronise(device: torch.device) -> None:
    """Wait for the GPU's queued work, so a clock reading means what it says."""
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _start_peak(device: torch.device) -> None:
    """Return cached blocks to the driver and restart the peak counters.

    Without emptying the cache first, the reserved peak would carry blocks an
    earlier measurement left cached.
    """
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)


def _peak(device: torch.device) -> tuple[int, int]:
    """The peak allocated and reserved bytes since the last restart; zeros off the GPU."""
    if device.type != "cuda":
        return 0, 0
    _synchronise(device)
    return torch.cuda.max_memory_allocated(device), torch.cuda.max_memory_reserved(device)


def _throughput(
    mode: str,
    *,
    batch_size: int,
    images: int,
    pass_seconds: list[float],
    peak: tuple[int, int],
    num_workers: int | None,
) -> Throughput:
    seconds = statistics.median(pass_seconds)
    return Throughput.model_validate(
        {
            "mode": mode,
            "batch_size": batch_size,
            "images": images,
            "pass_seconds": pass_seconds,
            "seconds": seconds,
            "images_per_second": images / seconds,
            "peak_allocated_bytes": peak[0],
            "peak_reserved_bytes": peak[1],
            "num_workers": num_workers,
        }
    )


def _timed_passes(
    model: MeasurableScorer, batches: list[torch.Tensor], *, repeats: int, warmup_batches: int
) -> list[float]:
    """Time passes over batches that are already on the model's device.

    The batches are this function's alone, so they are freed when it returns.
    """
    device = model.device
    for batch in (batches * warmup_batches)[:warmup_batches]:
        model.score(batch)
    _synchronise(device)
    pass_seconds: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        for batch in batches:
            model.score(batch)
        _synchronise(device)
        pass_seconds.append(time.perf_counter() - started)
    return pass_seconds


def measure_model(
    model: MeasurableScorer,
    images: torch.Tensor,
    *,
    batch_size: int,
    repeats: int = 3,
    warmup_batches: int = 3,
) -> Throughput:
    """Time the forward pass alone over a set of resized images.

    The timed passes run on batches already on the GPU, so the clock holds
    nothing but the model. The peak memory is taken on one more pass, after
    those batches are freed and the cache emptied, with one batch at a time
    copied from host memory: it is what inference holds, not the test set.

    Args:
        model: The trained model.
        images: Resized float images in [0, 1], as (count, 3, height, width),
            in host memory.
        batch_size: Images per forward pass.
        repeats: Timed passes over the set; the median is reported.
        warmup_batches: Batches scored before the clock starts.

    Returns:
        The throughput, and the peak GPU memory of a pass.

    Raises:
        ValueError: If there are no images.
    """
    if images.shape[0] == 0:
        msg = "no images to measure throughput on"
        raise ValueError(msg)
    device = model.device
    starts = range(0, images.shape[0], batch_size)
    pass_seconds = _timed_passes(
        model,
        [images[start : start + batch_size].to(device) for start in starts],
        repeats=repeats,
        warmup_batches=warmup_batches,
    )
    _start_peak(device)
    for start in starts:
        model.score(images[start : start + batch_size])
    return _throughput(
        "model",
        batch_size=batch_size,
        images=images.shape[0],
        pass_seconds=pass_seconds,
        peak=_peak(device),
        num_workers=None,
    )


def measure_end_to_end(
    model: MeasurableScorer,
    items: Sequence[InferenceItem],
    *,
    batch_size: int,
    num_workers: int = 8,
    repeats: int = 3,
    warmup_batches: int = 3,
) -> Throughput:
    """Time scoring from the image files to scores and maps in host memory.

    Each pass starts its own data loader, so worker start-up is inside the
    clock, as it is for a real batch of boards.

    Args:
        model: The trained model.
        items: The images to score.
        batch_size: Images per forward pass.
        num_workers: Data loader workers decoding and resizing images.
        repeats: Passes over the set; the median is reported.
        warmup_batches: Batches scored before the clock starts.

    Returns:
        The throughput and the peak GPU memory over the timed passes.

    Raises:
        ValueError: If there are no images.
    """
    if not items:
        msg = "no images to measure throughput on"
        raise ValueError(msg)
    device = model.device
    dataset = image_dataset([item.path for item in items], model.resize)

    def one_pass(limit: int | None = None) -> None:
        loader = DataLoader(dataset, batch_size=batch_size, num_workers=num_workers, shuffle=False)
        for number, (images, _) in enumerate(loader):
            if limit is not None and number >= limit:
                break
            scores, maps = model.score(images)
            scores.cpu()
            maps.cpu()

    one_pass(limit=warmup_batches)
    _synchronise(device)
    _start_peak(device)
    pass_seconds: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        one_pass()
        _synchronise(device)
        pass_seconds.append(time.perf_counter() - started)
    return _throughput(
        "end_to_end",
        batch_size=batch_size,
        images=len(items),
        pass_seconds=pass_seconds,
        peak=_peak(device),
        num_workers=num_workers,
    )


def measure(
    model: MeasurableScorer,
    items: Sequence[InferenceItem],
    category_dir: Path,
    *,
    device: CudaDevice,
    batch_sizes: Sequence[int] = BATCH_SIZES,
    num_workers: int = 8,
    repeats: int = 3,
) -> InferenceBench:
    """Measure a model's throughput both ways at each batch size, and write the record.

    Args:
        model: The trained model.
        items: The images to measure on, the category's test split.
        category_dir: The category's directory under the runs root; the record
            is written there as `bench.json`.
        device: The GPU the model is on, for the record.
        batch_sizes: The batch sizes to measure.
        num_workers: Data loader workers for the end-to-end figure.
        repeats: Passes per figure.

    Returns:
        The record, as written.
    """
    dataset = image_dataset([item.path for item in items], model.resize)
    images = torch.stack([dataset[index][0] for index in range(len(items))])
    runs: list[Throughput] = []
    for batch_size in batch_sizes:
        runs.append(measure_model(model, images, batch_size=batch_size, repeats=repeats))
        runs.append(
            measure_end_to_end(
                model, items, batch_size=batch_size, num_workers=num_workers, repeats=repeats
            )
        )
    bench = InferenceBench(
        category=model.category,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        device=device,
        images=len(items),
        resident_bytes=model.resident_bytes,
        runs=runs,
    )
    category_dir.mkdir(parents=True, exist_ok=True)
    (category_dir / BENCH_NAME).write_text(bench.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return bench


def load_bench(category_dir: Path) -> InferenceBench | None:
    """Read a category's bench record, if it has one.

    Args:
        category_dir: The category's directory under the runs root.

    Returns:
        The record, or None if the category was never benchmarked.
    """
    path = category_dir / BENCH_NAME
    if not path.is_file():
        return None
    return InferenceBench.model_validate_json(path.read_text(encoding="utf-8"))
