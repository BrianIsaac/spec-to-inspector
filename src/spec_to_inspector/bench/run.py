"""The bench's run: the whole pipeline on the labelled set, timed, and scored by the protocol.

Three stages, as a user would go through them:

1. the specification's PDF is parsed, and the clause table that comes out
   must be the tracked one;
2. each part's trained anomaly model scores that part's VisA test split,
   anomalous and good, into a run directory of the bench's own;
3. every image is judged as `inspect` judges it, with two switches set: no
   correction is recalled (the empty store), and every question is asked
   with the server's prompt cache off (cold), so the answers repeat.

Then the figures of `eval/PROTOCOL.md` are counted. Nothing is trained, and
nothing is written outside the bench's own run directories. A run in which
the server could not be asked, a correction reached a prompt, or the labelled
set's region columns are not what the model's regions give, raises and
leaves no record.

What depends on the machine (the PDF parser, the trained models, `nvidia-smi`,
the server's process) is passed in, so the run itself is tested whole against
a stub model and a fake server.
"""

import gc
import os
import shutil
import subprocess
import time
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple, TypedDict

import httpx
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.records import ImageResult, RunIndex
from spec_to_inspector.bench.gpu import read_gpu_memory
from spec_to_inspector.bench.labels import ClauseLabel, Region1, read_labels, region1_types
from spec_to_inspector.bench.mapping import mapping_problems
from spec_to_inspector.bench.observe import Observation, observe
from spec_to_inspector.bench.record import (
    BenchRecord,
    InspectorMinutes,
    JudgeSetup,
    LabelledSet,
    Leak,
    PartRun,
    SpecificationStage,
    StageMemory,
    StageTimes,
    file_ref,
)
from spec_to_inspector.bench.score import score
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.inspect import DEFAULT_MAX_REGIONS, RESULT_NAME, judge_image
from spec_to_inspector.judge.timing import (
    GpuReading,
    GpuSampler,
    Spread,
    listening_pid,
    server_facts,
    spread,
)
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

if TYPE_CHECKING:
    # Anomalib takes about ten seconds to import, so it is loaded only where a model is.
    from spec_to_inspector.anomaly.infer import InferenceItem, Scorer

DEFAULT_BATCH: Final = "bench"
OWN_MINIMUM: Final = "the model's own minimum"
UNKNOWN: Final = "unknown"
_PROBE_TIMEOUT_SECONDS: Final = 5.0
_MIB: Final = 1024**2


class BenchError(RuntimeError):
    """The bench cannot be run as asked, or its run is void; the message says why."""


class LoadedModel(NamedTuple):
    """A part's trained anomaly model, with what its training recorded.

    Attributes:
        scorer: The model, ready to score images.
        trained_at: When it was trained, in UTC.
        fit_seconds: The fit time recorded then.
        train_peak_allocated_bytes: The peak GPU memory PyTorch had allocated
            in that training; None where it was not recorded.
        release: Gives back to the card what the model held. It is to be
            called once nothing refers to the model any more, so it must not
            refer to the model itself.
    """

    scorer: "Scorer"
    trained_at: str
    fit_seconds: float
    train_peak_allocated_bytes: int | None
    release: Callable[[], None]


ModelLoader = Callable[[str], LoadedModel]
"""Loads a part's trained model."""

Parser = Callable[[Path], Specification]
"""Parses a specification PDF into its clause table."""

Scoring = Callable[["Scorer", Sequence["InferenceItem"], Path], RunIndex]
"""Scores images with a model and writes the run directory; `anomaly.infer.run_inference`."""


class BenchPlan(BaseModel):
    """What a run of the bench is made of.

    Attributes:
        parts: The parts to run, in order.
        limit: Only the first so many anomalous and the first so many good
            test images of each part, for a trial run; None for all of them.
        batch: The name of the bench's run directory under each part.
        visa_dir: The dataset directory `data fetch` wrote.
        runs_dir: The root of the run directories.
        spec_pdf: The specification to parse.
        clause_table: The tracked clause table the parse must equal.
        labels: The labelled set.
        protocol: The protocol the figures follow; recorded by its digest.
        max_regions: The most areas per image to put to the judge.
        command: The command line, for the record.
    """

    model_config = ConfigDict(frozen=True)

    parts: tuple[str, ...]
    limit: int | None = None
    batch: str = DEFAULT_BATCH
    visa_dir: Path
    runs_dir: Path
    spec_pdf: Path
    clause_table: Path
    labels: Path
    protocol: Path
    max_regions: int = DEFAULT_MAX_REGIONS
    command: tuple[str, ...] = ()


def server_arguments(pid: int | None) -> tuple[str, ...] | None:
    """Read the command line of a process on this machine.

    Args:
        pid: The process, or None if it is not known.

    Returns:
        Its arguments, or None if they cannot be read.
    """
    if pid is None:
        return None
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    return tuple(part.decode(errors="replace") for part in raw.split(b"\0") if part)


def image_min_tokens(arguments: Sequence[str] | None) -> str:
    """Find the fewest tokens a llama.cpp server gives an image, from its command line.

    Args:
        arguments: The server's arguments, or None if they could not be read.

    Returns:
        The flag's value; `the model's own minimum` when the flag is absent;
        `unknown` when there are no arguments to read.
    """
    if arguments is None:
        return UNKNOWN
    flag = "--image-min-tokens"
    for position, argument in enumerate(arguments):
        if argument == flag and position + 1 < len(arguments):
            return arguments[position + 1]
        if argument.startswith(f"{flag}="):
            return argument.split("=", 1)[1]
    return OWN_MINIMUM


def reachable(url: str) -> bool:
    """Tell whether an HTTP server answers at a URL at all.

    Args:
        url: The judge's base URL.

    Returns:
        True for any HTTP response, whatever its status; false when no
        connection could be made.
    """
    try:
        httpx.get(f"{url}/models", timeout=_PROBE_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return False
    return True


def gpu_name() -> str | None:
    """Read the first card's name from `nvidia-smi`.

    Returns:
        The name, or None if `nvidia-smi` is absent or fails.
    """
    program = shutil.which("nvidia-smi")
    if program is None:
        return None
    try:
        done = subprocess.run(
            [program, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = done.stdout.strip().splitlines()
    return lines[0].strip() if lines else None


@dataclass(frozen=True)
class Probes:
    """How the run reads the machine it is on; replaced in tests.

    Attributes:
        read_gpu: Reads the card's memory in use and one process's, without a
            pipe: the data loader forks while the anomaly model's stage is sampled.
        own_pid: Gives the bench's own process.
        server_pid: Finds the process listening at the judge's URL.
        server_facts: Asks the server what it is serving.
        server_arguments: Reads a process's command line.
        reachable: Tells whether a server answers at a URL.
        gpu_name: Names the card.
        interval_seconds: The pause between memory readings.
    """

    read_gpu: Callable[[int | None], GpuReading] = read_gpu_memory
    own_pid: Callable[[], int] = os.getpid
    server_pid: Callable[[str], int | None] = listening_pid
    server_facts: Callable[[str], dict[str, str]] = server_facts
    server_arguments: Callable[[int | None], tuple[str, ...] | None] = server_arguments
    reachable: Callable[[str], bool] = reachable
    gpu_name: Callable[[], str | None] = gpu_name
    interval_seconds: float = 0.5


@contextmanager
def _sampling(probes: Probes, pid: int | None) -> Generator[GpuSampler]:
    """Sample the GPU's memory for one process for the length of a block.

    Args:
        probes: How the machine is read.
        pid: The process whose own memory is wanted.

    Yields:
        The sampler; its `memory` holds the peaks once the block has ended.
    """
    with GpuSampler(
        lambda: probes.read_gpu(pid), interval_seconds=probes.interval_seconds
    ) as sampler:
        yield sampler


def _memory(sampler: GpuSampler) -> StageMemory:
    """Lay a sampler's peaks out as a stage's memory.

    Args:
        sampler: The sampler, after its block.

    Returns:
        The stage's memory.
    """
    read = sampler.memory
    return StageMemory(
        process_peak_mib=read.server_peak_mib,
        card_peak_mib=read.gpu_peak_mib,
        card_before_mib=read.gpu_before_mib,
        samples=read.samples,
        interval_seconds=read.interval_seconds,
    )


def _spread(values: Sequence[float | int | None]) -> Spread | None:
    """Summarise the values there are.

    Args:
        values: Measured values; None where one was not given.

    Returns:
        Their spread, or None if there is none to summarise.
    """
    present = [float(value) for value in values if value is not None]
    return spread(present) if present else None


def parse_specification(plan: BenchPlan, parse: Parser) -> tuple[Specification, SpecificationStage]:
    """Parse the specification's PDF, timed, and hold it to the tracked clause table.

    Args:
        plan: The run's plan.
        parse: The parser.

    Returns:
        The parsed specification and the stage's record.

    Raises:
        BenchError: If the PDF or the tracked table cannot be read, the parse
            does not give the tracked table, or the mapping table of the
            labelled set is not that specification's.
    """
    try:
        tracked = read_clause_table(plan.clause_table)
    except (OSError, ValueError) as error:
        msg = f"the tracked clause table {plan.clause_table} cannot be read: {error}"
        raise BenchError(msg) from error
    started = time.perf_counter()
    try:
        parsed = parse(plan.spec_pdf)
    except (OSError, ValueError, RuntimeError) as error:
        msg = f"the specification {plan.spec_pdf} could not be parsed: {error}"
        raise BenchError(msg) from error
    seconds = time.perf_counter() - started
    if parsed != tracked:
        msg = (
            f"parsing {plan.spec_pdf} does not give the tracked clause table "
            f"{plan.clause_table}: render and parse the specification again "
            "(scripts/render_spec.sh) before measuring anything against it"
        )
        raise BenchError(msg)
    problems = mapping_problems(parsed)
    if problems:
        msg = "the mapping table is not this specification's: " + "; ".join(problems)
        raise BenchError(msg)
    stage = SpecificationStage(
        pdf=file_ref(plan.spec_pdf),
        clause_table=file_ref(plan.clause_table),
        title=parsed.title,
        pages=parsed.pages,
        clauses=len(parsed.clauses),
        headings=len({clause.heading_id for clause in parsed.clauses}),
        parse_seconds=seconds,
        equals_tracked_clause_table=True,
    )
    return parsed, stage


def _limited(items: Sequence["InferenceItem"], limit: int | None) -> list["InferenceItem"]:
    """Cut a part's test images down for a trial run.

    Args:
        items: The part's test images, in the split's order.
        limit: How many anomalous and how many good images to keep; None for all.

    Returns:
        The images kept, in the same order.
    """
    if limit is None:
        return list(items)
    kept: dict[str | None, int] = {}
    chosen: list[InferenceItem] = []
    for item in items:
        if kept.get(item.label, 0) < limit:
            kept[item.label] = kept.get(item.label, 0) + 1
            chosen.append(item)
    return chosen


def _results(directory: Path, index: RunIndex) -> dict[str, ImageResult]:
    """Read every image's sidecar of a run.

    Args:
        directory: The run's directory.
        index: The run's index.

    Returns:
        The sidecars by image id, in the run's order.
    """
    return {
        entry.image_id: ImageResult.model_validate_json(
            (directory / entry.image_id / RESULT_NAME).read_text(encoding="utf-8")
        )
        for entry in index.entries
    }


def _stale(labels: Sequence[ClauseLabel], results: dict[str, ImageResult]) -> list[str]:
    """Name the labelled images whose region columns are not what a run's region 1 lies on.

    Args:
        labels: One part's labels.
        results: That part's sidecars, by image id.

    Returns:
        The images, as `<part> <image id>`.
    """
    stale: list[str] = []
    for label in labels:
        under = region1_types(results[label.image_id])
        fresh = (
            under is None if label.region1 is Region1.NO_REGION else under == label.region1_types
        )
        if not fresh:
            stale.append(f"{label.part} {label.image_id}")
    return stale


class _Scored(NamedTuple):
    """What the anomaly model's stage leaves for one part."""

    run: PartRun
    directory: Path
    results: dict[str, ImageResult]


def score_part(
    plan: BenchPlan,
    part: str,
    labels: Sequence[ClauseLabel],
    *,
    models: ModelLoader,
    items: Sequence["InferenceItem"],
    scoring: Scoring,
    probes: Probes,
) -> _Scored:
    """Score one part's test images with its trained model, into the bench's own run.

    Args:
        plan: The run's plan.
        part: The part.
        labels: The part's labels among the images run.
        models: Opens the part's trained model.
        items: The images to score.
        scoring: Scores the images and writes the run directory.
        probes: How the machine is read.

    Returns:
        The stage's record, the run's directory and its sidecars.

    Raises:
        BenchError: If the labelled set's region columns are not what this
            model's regions give.
    """
    directory = plan.runs_dir / part / plan.batch
    started = time.perf_counter()
    loaded = models(part)
    load_seconds = time.perf_counter() - started
    trained_at, fit_seconds, peak, release = loaded[1:]
    try:
        with _sampling(probes, probes.own_pid()) as sampler:
            index = scoring(loaded.scorer, items, directory)
        thresholds = loaded.scorer.thresholds
    finally:
        # The judge's stage should find the card without this model on it: the last
        # reference goes first, and only then can the allocator hand its memory back.
        del loaded
        release()
    results = _results(directory, index)
    stale = _stale(labels, results)
    if stale:
        msg = (
            f"the labelled set's region columns are not what the {part} model's regions give "
            f"for {len(stale)} image(s) ({', '.join(stale[:5])}{'...' if len(stale) > 5 else ''}): "
            f"rebuild it with `uv run python -m spec_to_inspector.bench.labels --run {plan.batch}`"
        )
        raise BenchError(msg)
    flagged = [entry for entry in index.entries if entry.regions > 0]
    run = PartRun(
        part=part,
        run_directory=str(directory),
        images=index.images,
        good=index.labelled_good,
        anomalous=index.labelled_bad,
        flagged_good=sum(entry.label == "good" for entry in flagged),
        flagged_anomalous=sum(entry.label == "bad" for entry in flagged),
        image_threshold=thresholds.image,
        thresholds_tuned_on_test=thresholds.tuned_on_test,
        batch_size=index.options.batch_size,
        load_seconds=load_seconds,
        inference_seconds=index.seconds,
        seconds_per_image=index.seconds / index.images,
        model_trained_at=trained_at,
        fit_seconds=fit_seconds,
        train_peak_allocated_mib=None if peak is None else peak / _MIB,
        memory=_memory(sampler),
    )
    return _Scored(run, directory, results)


def judge_part(
    scored: _Scored,
    specification: Specification,
    client: ChatClient,
    *,
    max_regions: int,
    on_image: Callable[[Observation], None] | None = None,
) -> Iterator[Observation]:
    """Judge every image of one part's run, cold and with no correction recalled.

    Args:
        scored: The part's run, as the anomaly model's stage left it.
        specification: The parsed specification.
        client: The VLM server's client.
        max_regions: The most areas per image to put to the judge.
        on_image: Called with each image's observation as it is made.

    Yields:
        One observation per image, in the run's order.

    Raises:
        BenchError: If the server could not be asked about an area, or a
            correction stood in a prompt.
    """
    for image_id, result in scored.results.items():
        started = time.perf_counter()
        decision = judge_image(
            scored.directory / image_id,
            specification,
            client,
            max_regions=max_regions,
            cache_prompt=False,
        )
        seconds = time.perf_counter() - started
        unasked = next(
            (r for r in decision.regions if r.review_cause is Cause.SERVER_UNAVAILABLE), None
        )
        if unasked is not None:
            msg = (
                f"the judge at {client.url} could not be asked about {result.category} "
                f"{image_id}: {unasked.reason}. The run is void and nothing is written; start "
                "the server with scripts/serve_vlm.sh start and run the bench again"
            )
            raise BenchError(msg)
        observation = observe(decision, result, judge_seconds=seconds)
        if observation.corrections_in_prompt:
            msg = (
                f"a correction stood in a prompt of {result.category} {image_id}, which the "
                "protocol forbids: the run is void and nothing is written"
            )
            raise BenchError(msg)
        if on_image is not None:
            on_image(observation)
        yield observation


def stage_times(
    parse_seconds: float,
    runs: dict[str, PartRun],
    observations: Sequence[Observation],
    judge_stage_seconds: float,
) -> StageTimes:
    """Lay the run's times out by stage.

    Args:
        parse_seconds: The specification stage's time.
        runs: The anomaly model's stage, per part.
        observations: Every image of the run.
        judge_stage_seconds: The wall time of the judge's stage.

    Returns:
        The times.
    """
    flagged = [observation for observation in observations if observation.flagged]
    asked = [area for observation in flagged for area in observation.areas if area.asked]
    return StageTimes(
        parse_seconds=parse_seconds,
        anomaly_seconds_per_image={part: run.seconds_per_image for part, run in runs.items()},
        flagged_images=len(flagged),
        areas_asked=len(asked),
        areas_per_flagged_image=len(asked) / len(flagged) if flagged else None,
        measure_and_draw_seconds=_spread([o.judge_seconds - o.vlm_seconds for o in flagged]),
        vlm_seconds_per_area=_spread([area.seconds for area in asked]),
        vlm_seconds_per_flagged_image=_spread([o.vlm_seconds for o in flagged]),
        flagged_image_seconds=_spread(
            [runs[o.part].seconds_per_image + o.judge_seconds for o in flagged]
        ),
        judge_stage_seconds=judge_stage_seconds,
        prompt_tokens=_spread([area.prompt_tokens for area in asked]),
        completion_tokens=_spread([area.completion_tokens for area in asked]),
        output_tokens_per_second=_spread([area.tokens_per_second for area in asked]),
    )


def _say_nothing(_line: str) -> None:
    """Take a line of progress and drop it.

    Args:
        _line: The line.
    """


def run_bench(
    plan: BenchPlan,
    *,
    parse: Parser,
    models: ModelLoader,
    client: ChatClient,
    test_items: Callable[[Path, str], Sequence["InferenceItem"]],
    scoring: Scoring,
    probes: Probes | None = None,
    say: Callable[[str], None] | None = None,
) -> BenchRecord:
    """Run the whole pipeline on the labelled set and count the protocol's figures.

    Args:
        plan: What to run.
        parse: Parses the specification's PDF.
        models: Opens a part's trained anomaly model.
        client: The VLM server's client.
        test_items: Lists a part's VisA test split as inference items;
            `anomaly.infer.visa_test_items`.
        scoring: Scores images and writes a run; `anomaly.infer.run_inference`.
        probes: How the machine is read; the real machine by default.
        say: Called with a line of progress now and then.

    Returns:
        The run's record, not yet written anywhere.

    Raises:
        BenchError: If the run cannot be made as planned, or is void.
    """
    probes = probes or Probes()
    tell = say or _say_nothing
    if not probes.reachable(client.url):
        msg = (
            f"the judge at {client.url} cannot be reached: start it with scripts/serve_vlm.sh start"
        )
        raise BenchError(msg)
    try:
        labels = read_labels(plan.labels)
        protocol = file_ref(plan.protocol)
    except (OSError, ValueError) as error:
        raise BenchError(str(error)) from error

    specification, parsed = parse_specification(plan, parse)
    tell(
        f"Parsed {plan.spec_pdf} in {parsed.parse_seconds:.1f} s: {parsed.clauses} clauses "
        f"under {parsed.headings} headings, equal to {plan.clause_table}"
    )

    scored: dict[str, _Scored] = {}
    run_labels: list[ClauseLabel] = []
    for part in plan.parts:
        try:
            items = _limited(test_items(plan.visa_dir, part), plan.limit)
        except RuntimeError as error:
            raise BenchError(str(error)) from error
        ids = {item.image_id for item in items}
        part_labels = [label for label in labels if label.part == part and label.image_id in ids]
        try:
            scored[part] = score_part(
                plan,
                part,
                part_labels,
                models=models,
                items=items,
                scoring=scoring,
                probes=probes,
            )
        except RuntimeError as error:
            if isinstance(error, BenchError):
                raise
            raise BenchError(str(error)) from error
        run_labels.extend(part_labels)
        run = scored[part].run
        tell(
            f"{part}: scored {run.images} images in {run.inference_seconds:.1f} s into "
            f"{run.run_directory}; {run.flagged_anomalous} of {run.anomalous} anomalous and "
            f"{run.flagged_good} of {run.good} good boards flagged"
        )

    to_judge = sum(s.run.flagged_anomalous + s.run.flagged_good for s in scored.values())
    judged = 0
    started = time.perf_counter()

    def progress(observation: Observation) -> None:
        nonlocal judged
        if observation.flagged:
            judged += 1
            if judged % 25 == 0 or judged == to_judge:
                elapsed = time.perf_counter() - started
                tell(f"Judged {judged} of {to_judge} flagged images, {elapsed:.0f} s")

    server_pid = probes.server_pid(client.url)
    observations: list[Observation] = []
    with _sampling(probes, server_pid) as sampler:
        for part in plan.parts:
            observations.extend(
                judge_part(
                    scored[part],
                    specification,
                    client,
                    max_regions=plan.max_regions,
                    on_image=progress,
                )
            )
    judge_stage_seconds = time.perf_counter() - started

    runs = {part: scored[part].run for part in plan.parts}
    fit = {part: run.fit_seconds for part, run in runs.items()}
    now = datetime.now(UTC)
    whole = plan.limit is None and len(run_labels) == len(labels)
    return BenchRecord(
        measured_at=now.isoformat(timespec="seconds"),
        measured_on=now.astimezone().date().isoformat(),
        command=list(plan.command),
        parts=list(plan.parts),
        limit=plan.limit,
        partial=not whole,
        protocol=protocol,
        labels=LabelledSet(
            file=file_ref(plan.labels),
            images=len(run_labels),
            single_defect=sum(label.single for label in run_labels),
            multi_defect=sum(not label.single for label in run_labels),
        ),
        specification=parsed,
        judge=JudgeSetup(
            url=client.url,
            model=client.model,
            server=probes.server_facts(client.url),
            image_min_tokens=image_min_tokens(probes.server_arguments(server_pid)),
            gpu=probes.gpu_name(),
            max_regions=plan.max_regions,
        ),
        runs=runs,
        scores=score(run_labels, observations),
        times=stage_times(parsed.parse_seconds, runs, observations, judge_stage_seconds),
        judge_memory=_memory(sampler),
        inspector=InspectorMinutes(
            parse_seconds=parsed.parse_seconds,
            fit_seconds=fit,
            minutes_by_part={
                part: (parsed.parse_seconds + seconds) / 60 for part, seconds in fit.items()
            },
            minutes_all_parts=(parsed.parse_seconds + sum(fit.values())) / 60,
        ),
        leak=Leak(
            decisions=len(observations),
            with_corrections_in_prompt=sum(o.corrections_in_prompt for o in observations),
        ),
        observations=observations,
    )


def _release_gpu() -> None:
    """Collect what is no longer referred to and hand PyTorch's cached GPU memory back."""
    import torch  # noqa: PLC0415

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def trained_model(models_dir: Path, part: str) -> LoadedModel:
    """Load a part's trained PatchCore model.

    Args:
        models_dir: The root of the trained models.
        part: The part.

    Returns:
        The model with what its training recorded.

    Raises:
        BenchError: If the part has no trained model there.
    """
    # Anomalib takes about ten seconds to import, so it is loaded where a model is.
    from spec_to_inspector.anomaly.infer import AnomalyModel  # noqa: PLC0415
    from spec_to_inspector.anomaly.train import ModelNotTrainedError  # noqa: PLC0415

    try:
        model = AnomalyModel.load(models_dir, part)
    except ModelNotTrainedError as error:
        msg = f"{error}; train it with `spec-to-inspector train --category {part}`"
        raise BenchError(msg) from error
    record = model.record
    return LoadedModel(
        scorer=model,
        trained_at=record.created_at,
        fit_seconds=record.fit_seconds,
        train_peak_allocated_bytes=record.peak_allocated_bytes,
        release=_release_gpu,
    )


class Pipeline(TypedDict):
    """The machine-bound halves of a run, as `run_bench` takes them.

    Attributes:
        parse: Parses the specification's PDF.
        models: Opens a part's trained anomaly model.
        test_items: Lists a part's VisA test split as inference items.
        scoring: Scores images and writes a run.
    """

    parse: Parser
    models: ModelLoader
    test_items: Callable[[Path, str], Sequence["InferenceItem"]]
    scoring: Scoring


def laptop_pipeline(settings: Settings) -> Pipeline:
    """Give the real pipeline: docling on the CPU, the trained PatchCore models on the GPU.

    Args:
        settings: Where the models are, and docling's artefacts if they are local.

    Returns:
        The pipeline's halves for `run_bench`.
    """
    # Anomalib and docling each take seconds to import; the bench is the verb that needs both.
    from spec_to_inspector.anomaly.infer import run_inference, visa_test_items  # noqa: PLC0415
    from spec_to_inspector.spec.pdf import read_pdf  # noqa: PLC0415

    def parse(pdf: Path) -> Specification:
        return read_pdf(pdf, artifacts_dir=settings.docling_artifacts_dir).specification()

    def models(part: str) -> LoadedModel:
        return trained_model(settings.models_dir, part)

    def scoring(scorer: "Scorer", items: Sequence["InferenceItem"], directory: Path) -> RunIndex:
        return run_inference(scorer, items, directory)

    return Pipeline(parse=parse, models=models, test_items=visa_test_items, scoring=scoring)
