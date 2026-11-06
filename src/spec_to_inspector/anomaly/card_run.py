"""Stage II's anomaly figures on an Intel card: the same pipeline, the card's memory read around it.

`spec-to-inspector train` measures what the laptop measured, through PyTorch's own counters. This
command adds what those cannot give, and what the laptop's run did not need:

- **A warm-up before any clock.** The first use of a kernel compiles it. A small embedding, coreset
  and scoring pass runs twice first, and both are recorded, so what first use costs is a figure.
- **The whole card's memory around each stage**, from `xpu-smi`, every half second, because the
  plugin holding the card under OpenVINO is not PyTorch and keeps no such counters.
- **OpenVINO's path**, through the same `run_inference` and `measure` as PyTorch's.
- **The comparison board by board** of two runs, and of two models' memory banks.

    python -m spec_to_inspector.anomaly.card_run pytorch --all --root ~/week2/run-1
    python -m spec_to_inspector.anomaly.card_run openvino --all --root ~/week2/run-1
    python -m spec_to_inspector.anomaly.card_run compare --a runs-a --b runs-b --out scores.json
    python -m spec_to_inspector.anomaly.card_run banks --a models-a --b models-b --out banks.json
    python -m spec_to_inspector.anomaly.card_run boards --source a=runs/{part}/test --out boards.csv

Nothing here changes what the laptop's commands do, and it runs with `ZE_AFFINITY_MASK` set by the
caller: nothing here picks a card.
"""

import csv
import gc
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Final, Literal, NamedTuple, cast

import numpy as np
import torch
import typer
from anomalib.models.components import KCenterGreedy
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.infer import (
    MAP_NAME,
    InferenceItem,
    load_run_index,
    run_dir,
    run_inference,
    visa_test_items,
)
from spec_to_inspector.anomaly.model import SingleCopyPatchcore
from spec_to_inspector.anomaly.ov_model import (
    OPENVINO_DEVICE,
    OpenVinoModel,
    export_openvino,
)
from spec_to_inspector.anomaly.pipeline import train_and_score
from spec_to_inspector.anomaly.precision import full_float32
from spec_to_inspector.anomaly.records import InferenceBench, RunIndex
from spec_to_inspector.anomaly.results import collect, write_results
from spec_to_inspector.anomaly.throughput import BATCH_SIZES, measure
from spec_to_inspector.anomaly.train import (
    CHECKPOINT_NAME,
    DEFAULT_BACKBONE,
    IMAGE_SIZE,
    model_dir,
)
from spec_to_inspector.card_memory import GpuReading, read_xpu_memory
from spec_to_inspector.datasets.visa import PUBLISHED_COUNTS
from spec_to_inspector.device import ComputeDevice, describe_device, release_memory, synchronise
from spec_to_inspector.judge.timing import GpuMemory, GpuSampler, Spread, spread
from spec_to_inspector.settings import Settings

OPENVINO_RUN: Final = "test-openvino"
"""The batch name of OpenVINO's scored run, beside PyTorch's `test` under each part."""
OPENVINO_BENCH: Final = "openvino-bench.json"
SCORING_BATCH: Final = 16
"""The batch `InferenceOptions` scores a run at, by default, on the laptop as here."""
SAMPLE_SECONDS: Final = 0.5
WARM_UP_PASSES: Final = 2
_WARM_UP_IMAGES: Final = 32
_WORST_BOARDS: Final = 5
_BANK_CHUNK_ROWS: Final = 1024
_SAME_ROW_DISTANCE: Final = 0.01
"""Two bank rows nearer than this are one patch, against distances of about 30 to a threshold."""

ReadCard = Callable[[], GpuReading]


class CardStage(BaseModel):
    """One step of a run, with the card's memory around it.

    Attributes:
        name: The step.
        seconds: Its wall time.
        memory: What `xpu-smi` showed while it ran.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    seconds: float
    memory: GpuMemory


class CardRun(BaseModel):
    """`card-<backend>.json`: a run's warm-up and its parts' stages.

    Attributes:
        backend: What did the computing.
        measured_at: When the run ended, in UTC, ISO 8601.
        command: The command line.
        warm_up_seconds: The passes before any clock, in order; the first holds the compiling.
        properties: What the plugin said it compiled; empty for PyTorch.
        parts: Each part's stages, in order.
    """

    model_config = ConfigDict(frozen=True)

    backend: Literal["pytorch-xpu", "openvino"]
    measured_at: str
    command: list[str]
    warm_up_seconds: list[float]
    properties: dict[str, str] = {}
    parts: dict[str, list[CardStage]]


class WorstBoard(BaseModel):
    """A board on which two runs' scores are far apart.

    Attributes:
        image_id: The board.
        score_a: Its score in the first run.
        score_b: Its score in the second.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    score_a: float
    score_b: float


class PartComparison(BaseModel):
    """Two runs of one part, board by board, each under its own thresholds.

    Attributes:
        part: The part.
        boards: The boards in both runs.
        flagged_a: Boards the first run flagged.
        flagged_b: Boards the second run flagged.
        flag_differs: Boards flagged in one and not in the other.
        flag_differs_boards: Which they are.
        regions_differ: Boards with another number of regions.
        score_difference: The absolute difference of the raw image scores.
        map_difference_max: The largest absolute difference anywhere in any board's raw anomaly
            map; None where a run's maps are not on this machine.
        image_threshold_a: The first run's image threshold.
        image_threshold_b: The second's.
        image_auroc_a: The first run's image AUROC.
        image_auroc_b: The second's.
        worst: The boards with the largest difference of score.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    boards: int
    flagged_a: int
    flagged_b: int
    flag_differs: int
    flag_differs_boards: list[str]
    regions_differ: int
    score_difference: Spread
    map_difference_max: float | None
    image_threshold_a: float
    image_threshold_b: float
    image_auroc_a: float | None
    image_auroc_b: float | None
    worst: list[WorstBoard]


class Comparison(BaseModel):
    """A comparison of two sets of runs.

    Attributes:
        a: What the first set is.
        b: What the second set is.
        command: The command line.
        parts: Each part's comparison.
    """

    model_config = ConfigDict(frozen=True)

    a: str
    b: str
    command: list[str]
    parts: dict[str, PartComparison]


class BankComparison(BaseModel):
    """Two models' memory banks, row by row.

    Attributes:
        rows_a: The first bank's rows.
        rows_b: The second bank's rows.
        same_rows: Rows of the first with a row of the second within `same_row_distance`.
        same_row_distance: How near counts as the same patch.
        nearest_distance: The distance from each row of the first to the nearest of the second.
    """

    model_config = ConfigDict(frozen=True)

    rows_a: int
    rows_b: int
    same_rows: int
    same_row_distance: float
    nearest_distance: Spread


class BanksRecord(BaseModel):
    """`banks.json`: what training on another device did to the memory banks.

    Attributes:
        a: What the first set of models is.
        b: What the second set is.
        command: The command line.
        parts: Each part's comparison.
    """

    model_config = ConfigDict(frozen=True)

    a: str
    b: str
    command: list[str]
    parts: dict[str, BankComparison]


def own_card_reader() -> ReadCard:
    """Give the reader of this process's first card and its own share of it.

    Returns:
        The reader.
    """
    pid = os.getpid()
    return lambda: read_xpu_memory(pid)


def timed_stage[T](name: str, read: ReadCard, work: Callable[[], T]) -> tuple[T, CardStage]:
    """Run one step, timing it and sampling the card for as long as it lasts.

    Args:
        name: The step's name.
        read: Gives one reading of the card.
        work: The step.

    Returns:
        What the step returned, and its record.
    """
    with GpuSampler(read, interval_seconds=SAMPLE_SECONDS) as sampler:
        started = time.perf_counter()
        result = work()
        seconds = time.perf_counter() - started
    return result, CardStage(name=name, seconds=seconds, memory=sampler.memory)


def warm_up_pytorch(device: str, *, images: int = _WARM_UP_IMAGES) -> float:
    """Embed, select a coreset and score a few random images, so that first use is behind the clock.

    Training sets its own seed afterwards, so what this draws changes nothing that follows.

    Args:
        device: The device.
        images: How many images to embed.

    Returns:
        How long it took, in seconds.
    """
    target = torch.device(device)
    started = time.perf_counter()
    module = SingleCopyPatchcore(
        backbone=DEFAULT_BACKBONE,
        pre_processor=SingleCopyPatchcore.configure_pre_processor(image_size=IMAGE_SIZE),
        visualizer=False,
    ).to(target)
    network = cast("Any", module.model)
    transform = cast("Any", module.pre_processor).transform
    batch = transform(torch.rand(images, 3, *IMAGE_SIZE, device=target))
    with full_float32(), torch.no_grad():
        network.train()
        embedding = network(batch)
        network.memory_bank = KCenterGreedy(
            embedding=embedding, sampling_ratio=0.1
        ).sample_coreset()
        network.eval()
        network(batch)
    synchronise(target)
    del module, network, batch, embedding
    release_memory(target)
    return time.perf_counter() - started


def _command() -> list[str]:
    """Give this run's command line, for the record.

    Returns:
        The arguments as they were given.
    """
    return ["python", "-m", "spec_to_inspector.anomaly.card_run", *sys.argv[1:]]


def _now() -> str:
    """Give the time, for the record.

    Returns:
        The time in UTC, ISO 8601.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(path: Path, record: BaseModel) -> None:
    """Write a record as indented JSON.

    Args:
        path: The file, created with its directory if absent.
        record: The record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def run_pytorch(
    parts: tuple[str, ...], *, visa_dir: Path, models_dir: Path, runs_dir: Path, out: Path
) -> CardRun:
    """Train, score and measure each part on PyTorch XPU, with the laptop's settings.

    Each part goes through `train_and_score` three times, as the laptop's two commands did it:
    training with Anomalib's test pass, the scored run, then the throughput. The record is written
    after every part, so a run that stops leaves what it finished.

    Args:
        parts: The parts.
        visa_dir: The dataset directory.
        models_dir: The root for the trained models.
        runs_dir: The root for the runs.
        out: The record's file.

    Returns:
        The record.
    """
    read = own_card_reader()
    warm_up = [warm_up_pytorch("xpu") for _ in range(WARM_UP_PASSES)]
    stages: dict[str, list[CardStage]] = {}
    for part in parts:
        through = partial(
            train_and_score,
            part,
            visa_dir=visa_dir,
            models_dir=models_dir,
            runs_dir=runs_dir,
            device="xpu",
        )
        _, train = timed_stage("train", read, partial(through, infer=False))
        _, scored = timed_stage("score", read, partial(through, reuse=True))
        _, bench = timed_stage("bench", read, partial(through, reuse=True, infer=False, bench=True))
        stages[part] = [train, scored, bench]
        _write(out, _pytorch_record(warm_up, stages))
    return _pytorch_record(warm_up, stages)


def _pytorch_record(warm_up: list[float], stages: dict[str, list[CardStage]]) -> CardRun:
    """Lay out PyTorch's run as far as it has gone.

    Args:
        warm_up: The warm-up's passes.
        stages: The stages of the parts finished.

    Returns:
        The record.
    """
    return CardRun(
        backend="pytorch-xpu",
        measured_at=_now(),
        command=_command(),
        warm_up_seconds=warm_up,
        parts=stages,
    )


def _openvino_card(model: OpenVinoModel) -> ComputeDevice:
    """Describe the card OpenVINO holds without touching it through PyTorch.

    Args:
        model: The model, whose plugin has been asked what it compiled.

    Returns:
        The device for a bench record.
    """
    return ComputeDevice(
        kind="xpu",
        index=0,
        name=model.properties["device_name"],
        total_memory_bytes=0,
        torch_version=torch.__version__,
    )


class _OpenVinoPart(NamedTuple):
    """What one batch size of one part leaves behind.

    Attributes:
        steps: Its stages.
        first_use: How long the first request took, in seconds.
        bench: Its throughput.
        properties: What the plugin said it compiled.
    """

    steps: list[CardStage]
    first_use: float
    bench: InferenceBench
    properties: dict[str, str]


def _openvino_batch(
    part: str,
    batch_size: int,
    *,
    items: list[InferenceItem],
    models_dir: Path,
    runs_dir: Path,
    device: str,
) -> _OpenVinoPart:
    """Export, compile, warm up, score and measure one part at one batch size.

    Args:
        part: The part.
        batch_size: The batch of the graph.
        items: The part's test images.
        models_dir: The root the model was trained into.
        runs_dir: The root for the runs.
        device: The device, as OpenVINO names it.

    Returns:
        What it left behind; the graph is off the card when this returns.
    """
    read = own_card_reader()
    label = f"batch-{batch_size}"
    _, exported = timed_stage(
        f"export-{label}",
        read,
        partial(export_openvino, models_dir, part, batch_size=batch_size),
    )
    model, compiled = timed_stage(
        f"compile-{label}",
        read,
        partial(OpenVinoModel.load, models_dir, part, batch_size=batch_size, device=device),
    )
    first, first_use = timed_stage(f"first-use-{label}", read, model.first_use)
    steps = [exported, compiled, first_use]
    if batch_size == SCORING_BATCH:
        target = run_dir(runs_dir, part, OPENVINO_RUN)
        _, scored = timed_stage("score", read, partial(run_inference, model, items, target))
        steps.append(scored)
    bench, measured = timed_stage(
        f"bench-{label}",
        read,
        partial(
            measure,
            model,
            items,
            runs_dir / part / f"openvino-{label}",
            device=_openvino_card(model),
            batch_sizes=(batch_size,),
        ),
    )
    steps.append(measured)
    properties = model.properties
    del model
    gc.collect()
    return _OpenVinoPart(steps, first, bench, properties)


def run_openvino(
    parts: tuple[str, ...],
    *,
    visa_dir: Path,
    models_dir: Path,
    runs_dir: Path,
    out: Path,
    device: str = OPENVINO_DEVICE,
) -> CardRun:
    """Export each part's trained model and score and measure it through OpenVINO.

    The run at batch 16 is scored as the laptop's is, and throughput is measured at each batch
    with only that batch's graph on the card, so a peak is one graph's.

    Args:
        parts: The parts.
        visa_dir: The dataset directory.
        models_dir: The root the models were trained into.
        runs_dir: The root for the runs.
        out: The record's file.
        device: The device, as OpenVINO names it.

    Returns:
        The record.

    Raises:
        ValueError: If there are no parts to run.
    """
    if not parts:
        msg = "no parts to run"
        raise ValueError(msg)
    stages: dict[str, list[CardStage]] = {}
    warm_up: list[float] = []
    record: CardRun | None = None
    for part in parts:
        items = visa_test_items(visa_dir, part)
        done = [
            _openvino_batch(
                part, size, items=items, models_dir=models_dir, runs_dir=runs_dir, device=device
            )
            for size in sorted(BATCH_SIZES, reverse=True)
        ]
        _write(
            runs_dir / part / OPENVINO_BENCH,
            InferenceBench(
                category=part,
                created_at=_now(),
                device=done[0].bench.device,
                images=len(items),
                resident_bytes=done[0].bench.resident_bytes,
                runs=[run for batch in reversed(done) for run in batch.bench.runs],
            ),
        )
        stages[part] = [step for batch in done for step in batch.steps]
        warm_up.extend(batch.first_use for batch in done)
        record = CardRun(
            backend="openvino",
            measured_at=_now(),
            command=_command(),
            warm_up_seconds=warm_up,
            properties=done[0].properties,
            parts=stages,
        )
        _write(out, record)
    return cast("CardRun", record)


def _map_difference(a: Path, b: Path, image_ids: list[str]) -> float | None:
    """Find the largest difference between two runs' raw anomaly maps.

    Args:
        a: The first run's directory.
        b: The second run's directory.
        image_ids: The boards.

    Returns:
        The largest absolute difference, or None if a map is not on this machine.
    """
    largest = 0.0
    for image_id in image_ids:
        first, second = a / image_id / MAP_NAME, b / image_id / MAP_NAME
        if not first.is_file() or not second.is_file():
            return None
        one = cast("NDArray[np.float32]", np.load(first))
        other = cast("NDArray[np.float32]", np.load(second))
        largest = max(largest, float(np.abs(one - other).max()))
    return largest


def compare_part(part: str, a: Path, b: Path) -> PartComparison:
    """Compare two runs of a part, board by board.

    Args:
        part: The part.
        a: The first run's directory.
        b: The second run's directory.

    Returns:
        The comparison.

    Raises:
        ValueError: If the runs are not of the same boards.
    """
    first: RunIndex = load_run_index(a)
    second: RunIndex = load_run_index(b)
    other = {entry.image_id: entry for entry in second.entries}
    if set(other) != {entry.image_id for entry in first.entries}:
        msg = f"{a} and {b} are not runs of the same boards"
        raise ValueError(msg)
    pairs = [(entry, other[entry.image_id]) for entry in first.entries]
    ranked = sorted(pairs, key=lambda pair: abs(pair[0].score - pair[1].score), reverse=True)
    flipped = [one for one, two in pairs if one.predicted_anomalous != two.predicted_anomalous]
    return PartComparison(
        part=part,
        boards=len(pairs),
        flagged_a=sum(one.predicted_anomalous for one, _ in pairs),
        flagged_b=sum(two.predicted_anomalous for _, two in pairs),
        flag_differs=len(flipped),
        flag_differs_boards=[entry.image_id for entry in flipped],
        regions_differ=sum(one.regions != two.regions for one, two in pairs),
        score_difference=spread([abs(one.score - two.score) for one, two in pairs]),
        map_difference_max=_map_difference(a, b, [one.image_id for one, _ in pairs]),
        image_threshold_a=first.thresholds.image,
        image_threshold_b=second.thresholds.image,
        image_auroc_a=first.image_auroc,
        image_auroc_b=second.image_auroc,
        worst=[
            WorstBoard(image_id=one.image_id, score_a=one.score, score_b=two.score)
            for one, two in ranked[:_WORST_BOARDS]
        ],
    )


def compare_banks(a: torch.Tensor, b: torch.Tensor) -> BankComparison:
    """Compare two memory banks, finding for each row of one the nearest row of the other.

    `torch.cdist` finds the row, but its distances come from a matrix product whose float32 noise
    at these magnitudes is about 0.06 even between identical rows (measured: a median of exactly
    0.0625). So the distance reported is worked directly from the two rows it found.

    Args:
        a: The first bank, as (rows, values).
        b: The second bank, on the same device.

    Returns:
        The comparison.
    """
    nearest: list[NDArray[np.float32]] = []
    for start in range(0, a.shape[0], _BANK_CHUNK_ROWS):
        rows = a[start : start + _BANK_CHUNK_ROWS]
        found = b[torch.cdist(rows, b).argmin(dim=1)]
        distances = (rows - found).pow(2).sum(dim=1).sqrt()
        nearest.append(cast("NDArray[np.float32]", distances.numpy(force=True)))
    measured = np.concatenate(nearest)
    return BankComparison(
        rows_a=a.shape[0],
        rows_b=b.shape[0],
        same_rows=int((measured < _SAME_ROW_DISTANCE).sum()),
        same_row_distance=_SAME_ROW_DISTANCE,
        nearest_distance=spread([float(value) for value in measured]),
    )


def write_boards(sources: dict[str, Path], parts: tuple[str, ...], out: Path) -> int:
    """Write every board's score, flag and region count in each run, one line to a board.

    Args:
        sources: Each column group's name and its run's directory, with `{part}` for the part.
        parts: The parts.
        out: The CSV file.

    Returns:
        How many boards were written.
    """
    head = ["part", "image_id", "label"]
    for name in sources:
        head += [f"{name}_score", f"{name}_flagged", f"{name}_regions"]
    rows: list[list[str]] = []
    for part in parts:
        indices = [load_run_index(Path(str(path).format(part=part))) for path in sources.values()]
        lookups = [{entry.image_id: entry for entry in index.entries} for index in indices]
        for first in indices[0].entries:
            row = [part, first.image_id, first.label or ""]
            for lookup in lookups:
                entry = lookup[first.image_id]
                row += [repr(entry.score), str(int(entry.predicted_anomalous)), str(entry.regions)]
            rows.append(row)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(head)
        writer.writerows(rows)
    return len(rows)


def _bank(models_dir: Path, part: str, device: torch.device) -> torch.Tensor:
    """Read a trained model's memory bank from its checkpoint.

    Args:
        models_dir: The root for trained models.
        part: The part.
        device: Where to put it.

    Returns:
        The bank.
    """
    checkpoint = model_dir(models_dir, part) / CHECKPOINT_NAME
    loaded = cast(
        "dict[str, dict[str, torch.Tensor]]",
        torch.load(checkpoint, map_location="cpu", weights_only=False),
    )
    return loaded["state_dict"]["model.memory_bank"].to(device)


app = typer.Typer(add_completion=False, help=__doc__)
_PARTS: Final = tuple(PUBLISHED_COUNTS)

PartOption = Annotated[
    list[str] | None, typer.Option("--part", help="A part; all four if none is given.")
]
RootOption = Annotated[
    Path, typer.Option("--root", help="Holds this run's models/, runs/ and records.")
]


def _chosen(part: list[str] | None) -> tuple[str, ...]:
    """Give the parts a command is to run.

    Args:
        part: The parts named, if any.

    Returns:
        Those parts, or all four.
    """
    return tuple(part) if part else _PARTS


@app.command()
def pytorch(root: RootOption, part: PartOption = None) -> None:
    """Train, score and measure on PyTorch XPU, into a root of its own."""
    settings = Settings()
    parts = _chosen(part)
    models_dir, runs_dir = root / "models", root / "runs"
    run_pytorch(
        parts,
        visa_dir=settings.visa_dir,
        models_dir=models_dir,
        runs_dir=runs_dir,
        out=root / "card-pytorch.json",
    )
    write_results(
        root / "anomaly.json",
        collect(parts, models_dir=models_dir, runs_dir=runs_dir, written_by=_command()),
    )


@app.command()
def openvino(
    root: RootOption,
    part: PartOption = None,
    device: Annotated[
        str, typer.Option("--device", help="The device, as OpenVINO names it.")
    ] = OPENVINO_DEVICE,
) -> None:
    """Export the root's trained models and score and measure them through OpenVINO."""
    run_openvino(
        _chosen(part),
        visa_dir=Settings().visa_dir,
        models_dir=root / "models",
        runs_dir=root / "runs",
        out=root / "card-openvino.json",
        device=device,
    )


@app.command()
def compare(
    a: Annotated[Path, typer.Option("--a", help="The first runs root.")],
    b: Annotated[Path, typer.Option("--b", help="The second runs root.")],
    out: Annotated[Path, typer.Option("--out", help="The record's file.")],
    a_batch: Annotated[str, typer.Option(help="The first root's run under each part.")] = "test",
    b_batch: Annotated[str, typer.Option(help="The second root's run under each part.")] = "test",
    a_label: Annotated[str, typer.Option(help="What the first root is.")] = "",
    b_label: Annotated[str, typer.Option(help="What the second root is.")] = "",
    part: PartOption = None,
) -> None:
    """Compare two sets of runs, board by board."""
    _write(
        out,
        Comparison(
            a=a_label or str(a),
            b=b_label or str(b),
            command=_command(),
            parts={
                name: compare_part(name, run_dir(a, name, a_batch), run_dir(b, name, b_batch))
                for name in _chosen(part)
            },
        ),
    )


@app.command()
def boards(
    source: Annotated[
        list[str],
        typer.Option(help="name=directory of a run, with {part} for the part. May be repeated."),
    ],
    out: Annotated[Path, typer.Option("--out", help="The CSV file.")],
    part: PartOption = None,
) -> None:
    """Write every board's score, flag and region count in each run, to one CSV."""
    named = dict(item.split("=", 1) for item in source)
    write_boards({name: Path(path) for name, path in named.items()}, _chosen(part), out)


@app.command()
def banks(
    a: Annotated[Path, typer.Option("--a", help="The first models root.")],
    b: Annotated[Path, typer.Option("--b", help="The second models root.")],
    out: Annotated[Path, typer.Option("--out", help="The record's file.")],
    a_label: Annotated[str, typer.Option(help="What the first root is.")] = "",
    b_label: Annotated[str, typer.Option(help="What the second root is.")] = "",
    part: PartOption = None,
) -> None:
    """Compare two sets of models' memory banks, on this machine's first card."""
    describe_device("xpu")
    target = torch.device("xpu")
    parts: dict[str, BankComparison] = {}
    for name in _chosen(part):
        parts[name] = compare_banks(_bank(a, name, target), _bank(b, name, target))
        release_memory(target)
    _write(
        out,
        BanksRecord(a=a_label or str(a), b=b_label or str(b), command=_command(), parts=parts),
    )


if __name__ == "__main__":
    app()
