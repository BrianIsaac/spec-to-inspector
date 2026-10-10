"""The judge's measured figures: answer time cold and cached, tokens, GPU memory.

One command measures them on a run the anomaly model wrote and records them
in `results/stage1/judge.json`:

    uv run python -m spec_to_inspector.judge.timing --category pcb4 --images 24

Each of the first N flagged images of the run is put to the judge twice, its
most anomalous region only:

- **cold**: with the server's prompt cache switched off for the request, so
  the whole prompt is evaluated, clause table included;
- **cached**: with the cache on, after one warm-up request on another image,
  so the prefix the images share (the instructions, the clause table, the
  part's headings and the corrections slot) is taken from the cache and only
  the measured facts and the two pictures are evaluated.

The time is the request's wall time as the client saw it. While the run goes
on, `nvidia-smi` is sampled for the server process's memory and the card's.
Nothing is written into the run: no decision, no overlay.
"""

import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Annotated, Final, Literal, NamedTuple, Self, cast
from urllib.parse import urlsplit

import httpx
import numpy as np
import typer
from pydantic import BaseModel, ConfigDict, Field

from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import judge_image, read_run_index
from spec_to_inspector.judge.prompt import clause_prefix
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table
from spec_to_inspector.spec.tokens import count_tokens

RESULTS_SCHEMA_VERSION: Final = 1
DEFAULT_IMAGES: Final = 24
DEFAULT_RESULTS: Final = Path("results/stage1/judge.json")
_SMI_TIMEOUT_SECONDS: Final = 5.0

NOTES: Final[dict[str, str]] = {
    "units": (
        "seconds are wall time of one chat-completion request as the client saw it; tokens are "
        "the server's own counts, images included; memory is MiB as nvidia-smi reports it"
    ),
    "cold": (
        "the request sent with cache_prompt false: the whole prompt is evaluated, clause table "
        "included"
    ),
    "cached": (
        "the request sent with the server's prompt cache on, after one warm-up request on "
        "another image: the prefix the images share is not evaluated again"
    ),
    "percentiles": "numpy.percentile, linear interpolation between the ranked values",
    "one_region": "each image is asked once per pass, about its most anomalous region only",
    "live": (
        "the answers of the marked live test, uv run pytest -m live: region decisions on real "
        "crops, recorded as they came; ground_truth is VisA's defect type under region 1"
    ),
}


class TimingError(RuntimeError):
    """The figures cannot be measured as asked; the message says why."""


class Spread(BaseModel):
    """How a measured quantity is distributed over the images.

    Attributes:
        n: How many values.
        p50: The median.
        p95: The 95th percentile.
        mean: The mean.
        minimum: The smallest value.
        maximum: The largest value.
    """

    model_config = ConfigDict(frozen=True)

    n: int = Field(ge=1)
    p50: float
    p95: float
    mean: float
    minimum: float
    maximum: float


def spread(values: Sequence[float]) -> Spread:
    """Summarise measured values.

    Args:
        values: The values, in any order.

    Returns:
        Their count, median, 95th percentile, mean and range.

    Raises:
        ValueError: If there are no values.
    """
    if not values:
        msg = "no values to summarise"
        raise ValueError(msg)
    array = np.asarray(values, dtype=np.float64)
    return Spread(
        n=len(values),
        p50=float(np.percentile(array, 50)),
        p95=float(np.percentile(array, 95)),
        mean=float(array.mean()),
        minimum=float(array.min()),
        maximum=float(array.max()),
    )


def _spread_of(values: Sequence[float | None]) -> Spread | None:
    """Summarise the values a server gave, if it gave any.

    Args:
        values: One value per request; None where the server said nothing.

    Returns:
        The spread of the values present, or None if none are.
    """
    present = [value for value in values if value is not None]
    return spread(present) if present else None


class Sample(BaseModel):
    """One image's question in one pass.

    Attributes:
        image_id: The image.
        seconds: Wall time of the requests for it, as the client saw it.
        attempts: Requests sent: one, or two when the first answer was refused.
        prompt_tokens: Tokens in the prompt, images included.
        cached_tokens: Prompt tokens the server took from its cache.
        completion_tokens: Tokens generated.
        tokens_per_second: The server's generation rate.
        outcome: What the region was decided as.
        review_cause: Why it was referred, if it was.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    seconds: float
    attempts: int
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    completion_tokens: int | None = None
    tokens_per_second: float | None = None
    outcome: Outcome
    review_cause: Cause | None = None


class GpuMemory(BaseModel):
    """What `nvidia-smi` showed while the run went on.

    Attributes:
        server_peak_mib: The most memory the VLM server's own process held,
            found by the pid listening on the judge's port; None if that
            process is not on this machine's card.
        gpu_peak_mib: The most memory in use on the card, by every process.
        gpu_before_mib: The memory in use on the card at the first sample.
        samples: How many times `nvidia-smi` was read.
        interval_seconds: The pause between readings.
    """

    model_config = ConfigDict(frozen=True)

    server_peak_mib: int | None = None
    gpu_peak_mib: int | None = None
    gpu_before_mib: int | None = None
    samples: int = 0
    interval_seconds: float


class GpuReading(NamedTuple):
    """One reading of `nvidia-smi`.

    Attributes:
        gpu_used_mib: Memory in use on the card, or None if unreadable.
        server_mib: Memory the VLM server's own process holds, or None if
            the process is not known or not among the card's.
    """

    gpu_used_mib: int | None
    server_mib: int | None


def _mib(text: str) -> int | None:
    """Read a figure of `nvidia-smi`.

    Args:
        text: One field of its CSV output.

    Returns:
        The integer, or None for anything else, such as `N/A`.
    """
    stripped = text.strip()
    return int(stripped) if stripped.isdigit() else None


def parse_nvidia_smi(gpu_text: str, apps_text: str, server_pid: int | None) -> GpuReading:
    """Read the two `nvidia-smi` queries the sampler makes.

    Args:
        gpu_text: The output of `--query-gpu=memory.used`, one card per line.
        apps_text: The output of `--query-compute-apps=pid,used_memory`.
        server_pid: The VLM server's process, or None if it is not known.

    Returns:
        The first card's memory in use and the server process's own.
    """
    lines = gpu_text.strip().splitlines()
    server: int | None = None
    for row in apps_text.strip().splitlines():
        fields = [field.strip() for field in row.split(",")]
        if server_pid is not None and fields[0] == str(server_pid):
            server = _mib(fields[-1])
    return GpuReading(gpu_used_mib=_mib(lines[0]) if lines else None, server_mib=server)


def parse_listening_pid(ss_text: str) -> int | None:
    """Read the process that listens on a port from `ss -ltnpH`'s output.

    Args:
        ss_text: The output, one listening socket per line.

    Returns:
        The first listener's pid, or None if there is none or it is not shown.
    """
    found = re.search(r"pid=(\d+)", ss_text)
    return int(found.group(1)) if found else None


def listening_pid(url: str) -> int | None:
    """Find the process on this machine that listens on a server URL's port.

    Args:
        url: The server's URL.

    Returns:
        The listener's pid; None if nothing here listens on the port, as for
        a server on another machine, or `ss` is absent.
    """
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    program = shutil.which("ss")
    if program is None:
        return None
    try:
        done = subprocess.run(
            [program, "-ltnpH", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=_SMI_TIMEOUT_SECONDS,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_listening_pid(done.stdout)


def read_nvidia_smi(server_pid: int | None = None) -> GpuReading:
    """Read the card's memory in use and the server process's, through `nvidia-smi`.

    Args:
        server_pid: The VLM server's process, or None if it is not known.

    Returns:
        The reading; both figures None if `nvidia-smi` is absent or fails.
    """
    program = shutil.which("nvidia-smi")
    if program is None:
        return GpuReading(None, None)
    outputs: list[str] = []
    for query in ("--query-gpu=memory.used", "--query-compute-apps=pid,used_memory"):
        try:
            done = subprocess.run(
                [program, query, "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=_SMI_TIMEOUT_SECONDS,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return GpuReading(None, None)
        outputs.append(done.stdout)
    return parse_nvidia_smi(outputs[0], outputs[1], server_pid)


class GpuSampler:
    """Reads the GPU's memory at an interval for as long as it is entered."""

    def __init__(
        self,
        read: Callable[[], GpuReading] = read_nvidia_smi,
        *,
        interval_seconds: float = 0.5,
    ) -> None:
        """Set what is read and how often.

        Args:
            read: Gives one reading.
            interval_seconds: The pause between readings.
        """
        self._read = read
        self._interval = interval_seconds
        self._readings: list[GpuReading] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        """Read until told to stop, once at least."""
        while True:
            self._readings.append(self._read())
            if self._stop.wait(self._interval):
                return

    def __enter__(self) -> Self:
        """Start sampling.

        Returns:
            The sampler.
        """
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Stop sampling."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    @property
    def samples(self) -> int:
        """How many readings have been taken."""
        return len(self._readings)

    @property
    def memory(self) -> GpuMemory:
        """The peaks over the readings taken so far."""
        readings = list(self._readings)
        server = [r.server_mib for r in readings if r.server_mib is not None]
        card = [r.gpu_used_mib for r in readings if r.gpu_used_mib is not None]
        return GpuMemory(
            server_peak_mib=max(server) if server else None,
            gpu_peak_mib=max(card) if card else None,
            gpu_before_mib=readings[0].gpu_used_mib if readings else None,
            samples=len(readings),
            interval_seconds=self._interval,
        )


class Timing(BaseModel):
    """The judge's answer time, tokens and memory over the images of one run.

    Attributes:
        measured_at: When the run ended, in UTC, ISO 8601.
        command: The command that measured it.
        category: The part.
        run: The run directory the images came from.
        specification: The specification's title.
        judge_url: The VLM server asked.
        judge_model: The model's name on that server.
        server: What the server says of itself: its build, its model, its context.
        label: What the server was started with that it does not report, in
            the operator's words, such as its image-token floor.
        images: How many images were asked, each once per pass.
        clause_prefix_tokens: The system message (instructions and clause
            table) in the judge's tokenizer; text only, exact.
        cold_seconds: Answer time with the prompt cache off.
        cached_seconds: Answer time with the clause prefix cached.
        warm_up_seconds: The one request before the cached pass, not counted in it.
        prompt_tokens: Prompt tokens per request, images included (cached pass).
        cached_prompt_tokens: Prompt tokens taken from the cache (cached pass).
        completion_tokens: Tokens generated per request (cached pass).
        output_tokens_per_second: The server's generation rate (cached pass).
        gpu: The GPU's memory while the run went on.
        cold: The cold pass, image by image.
        cached: The cached pass, image by image.
    """

    model_config = ConfigDict(frozen=True)

    measured_at: str
    command: list[str]
    category: str
    run: str
    specification: str
    judge_url: str
    judge_model: str
    server: dict[str, str] = Field(default_factory=dict)
    label: str = ""
    images: int
    clause_prefix_tokens: int
    cold_seconds: Spread
    cached_seconds: Spread
    warm_up_seconds: float
    prompt_tokens: Spread | None = None
    cached_prompt_tokens: Spread | None = None
    completion_tokens: Spread | None = None
    output_tokens_per_second: Spread | None = None
    gpu: GpuMemory
    cold: list[Sample]
    cached: list[Sample]


class LiveAnswer(BaseModel):
    """One image of the marked live test, as the real model answered it.

    Attributes:
        image_id: The image.
        label: VisA's label for the board, "good" or "bad".
        ground_truth: VisA's defect types under the image's region 1; empty
            for a good board or a region on no labelled defect.
        regions_found: Regions in the anomaly model's result.
        regions_judged: Regions put to the judge.
        outcome: The board's outcome.
        reason: The decision's reason, written by code.
        review_cause: Why it was referred, if it was.
        clause_id: The clause applied to the deciding region.
        judge_reason: The model's own line about region 1.
        judge_defect_class: The class the model named for region 1.
        judge_clause_id: The heading the model cited for region 1.
        seconds: Wall time of the requests for region 1.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    label: str | None = None
    ground_truth: list[str] = Field(default_factory=list)
    regions_found: int
    regions_judged: int
    outcome: Outcome
    reason: str
    review_cause: Cause | None = None
    clause_id: str | None = None
    judge_reason: str | None = None
    judge_defect_class: str | None = None
    judge_clause_id: str | None = None
    seconds: float | None = None


class LiveRecord(BaseModel):
    """The marked live test's answers.

    Attributes:
        measured_at: When the test ran, in UTC, ISO 8601.
        command: The command that ran it.
        category: The part.
        run: The run directory the images came from.
        judge_url: The VLM server asked.
        judge_model: The model's name on that server.
        answers: One per image, in the order judged.
    """

    model_config = ConfigDict(frozen=True)

    measured_at: str
    command: list[str]
    category: str
    run: str
    judge_url: str
    judge_model: str
    answers: list[LiveAnswer]


class JudgeResults(BaseModel):
    """`results/stage1/judge.json`: the judge's figures, each section with its own writer.

    Attributes:
        schema_version: The version of this file's layout.
        notes: What the figures mean and their units.
        timing: The timing run's figures.
        live: The marked live test's answers.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = RESULTS_SCHEMA_VERSION
    notes: dict[str, str] = Field(default_factory=lambda: dict(NOTES))
    timing: Timing | None = None
    live: LiveRecord | None = None


def read_results(path: Path) -> JudgeResults:
    """Read the figures file.

    Args:
        path: The file.

    Returns:
        Its content, or an empty record if there is no file yet.
    """
    if not path.is_file():
        return JudgeResults()
    return JudgeResults.model_validate_json(path.read_text(encoding="utf-8"))


def update_results(
    path: Path, *, timing: Timing | None = None, live: LiveRecord | None = None
) -> JudgeResults:
    """Replace the sections given in the figures file and keep the others.

    Args:
        path: The file, created with its directory if absent.
        timing: The timing run's figures, if they are to be replaced.
        live: The live test's answers, if they are to be replaced.

    Returns:
        The file's content as written.
    """
    current = read_results(path)
    updated = JudgeResults(
        timing=timing if timing is not None else current.timing,
        live=live if live is not None else current.live,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return updated


def server_facts(url: str) -> dict[str, str]:
    """Ask a llama.cpp server what it is serving.

    Args:
        url: The server's base URL, up to and including `/v1`.

    Returns:
        Its model's alias, file and quantisation, its build, its slots and its
        context, each as text; empty for a server that has no `/props` or
        cannot be reached.
    """
    try:
        response = httpx.get(f"{url.removesuffix('/v1')}/props", timeout=_SMI_TIMEOUT_SECONDS)
        payload: object = response.json() if response.is_success else {}
    except (httpx.HTTPError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    props = cast("dict[str, object]", payload)
    settings = props.get("default_generation_settings")
    context = (
        cast("dict[str, object]", settings).get("n_ctx") if isinstance(settings, dict) else None
    )
    model_path = props.get("model_path")
    found: dict[str, object | None] = {
        "model_alias": props.get("model_alias"),
        "model_file": Path(model_path).name if isinstance(model_path, str) else None,
        "model_ftype": props.get("model_ftype"),
        "build_info": props.get("build_info"),
        "total_slots": props.get("total_slots"),
        "n_ctx": context,
    }
    return {key: str(value) for key, value in found.items() if value is not None}


def _sample(decision: Decision) -> Sample:
    """Take the timing of an image's one question from its decision.

    Args:
        decision: The decision on the image, with its first region judged.

    Returns:
        The sample.

    Raises:
        TimingError: If the judge was not asked, or could not be.
    """
    region = decision.regions[0] if decision.regions else None
    call = None if region is None else region.call
    if region is None or call is None:
        msg = f"{decision.image_id} was not put to the judge: {decision.reason}"
        raise TimingError(msg)
    if region.review_cause is Cause.SERVER_UNAVAILABLE:
        msg = f"{decision.image_id}: {call.error}"
        raise TimingError(msg)
    return Sample(
        image_id=decision.image_id,
        seconds=call.seconds,
        attempts=call.attempts,
        prompt_tokens=call.prompt_tokens,
        cached_tokens=call.cached_tokens,
        completion_tokens=call.completion_tokens,
        tokens_per_second=call.tokens_per_second,
        outcome=region.outcome,
        review_cause=region.review_cause,
    )


def measure(
    run_directory: Path,
    specification: Specification,
    client: ChatClient,
    *,
    images: int = DEFAULT_IMAGES,
    sampler: GpuSampler | None = None,
    command: Sequence[str] = (),
    server: dict[str, str] | None = None,
    label: str = "",
) -> Timing:
    """Time the judge on the first flagged images of a run, cold and cached.

    Args:
        run_directory: A run the anomaly model wrote.
        specification: The parsed specification.
        client: The VLM server's client.
        images: How many flagged images to ask, each once per pass.
        sampler: Reads the GPU's memory during the run; if None, `nvidia-smi`
            every half second, for the card and for the process listening on
            the client's port.
        command: The command line, for the record.
        server: What the server says of itself, for the record.
        label: What the server was started with that it does not report.

    Returns:
        The figures.

    Raises:
        TimingError: If the run holds fewer flagged images than asked for, or
            the judge cannot be asked.
    """
    index = read_run_index(run_directory)
    flagged = [entry.image_id for entry in index.entries if entry.regions > 0]
    if len(flagged) < images or images < 1:
        msg = f"the run {run_directory} has {len(flagged)} flagged images, not the {images} asked"
        raise TimingError(msg)
    chosen = flagged[:images]

    def ask(image_id: str, *, cache_prompt: bool | None) -> Sample:
        return _sample(
            judge_image(
                run_directory / image_id,
                specification,
                client,
                max_regions=1,
                cache_prompt=cache_prompt,
                write=False,
            )
        )

    server_pid = listening_pid(client.url) if sampler is None else None
    watching = sampler if sampler is not None else GpuSampler(lambda: read_nvidia_smi(server_pid))
    with watching:
        cold = [ask(image_id, cache_prompt=False) for image_id in chosen]
        warm_up = ask(chosen[-1], cache_prompt=None)
        cached = [ask(image_id, cache_prompt=None) for image_id in chosen]

    return Timing(
        measured_at=datetime.now(UTC).isoformat(timespec="seconds"),
        command=list(command),
        category=index.category,
        run=str(run_directory),
        specification=specification.title,
        judge_url=client.url,
        judge_model=client.model,
        server=server or {},
        label=label,
        images=len(chosen),
        clause_prefix_tokens=count_tokens(clause_prefix(specification)),
        cold_seconds=spread([sample.seconds for sample in cold]),
        cached_seconds=spread([sample.seconds for sample in cached]),
        warm_up_seconds=warm_up.seconds,
        prompt_tokens=_spread_of([sample.prompt_tokens for sample in cached]),
        cached_prompt_tokens=_spread_of([sample.cached_tokens for sample in cached]),
        completion_tokens=_spread_of([sample.completion_tokens for sample in cached]),
        output_tokens_per_second=_spread_of([sample.tokens_per_second for sample in cached]),
        gpu=watching.memory,
        cold=cold,
        cached=cached,
    )


def main(
    category: Annotated[
        str, typer.Option("--category", "-c", help="The part whose run is timed, such as pcb4.")
    ],
    images: Annotated[
        int, typer.Option("--images", min=1, help="Flagged images to ask, each once per pass.")
    ] = DEFAULT_IMAGES,
    run: Annotated[
        Path | None,
        typer.Option("--run", help="The run directory; <runs-dir>/<category>/test by default."),
    ] = None,
    spec: Annotated[Path, typer.Option("--spec", help="The specification's clause table.")] = Path(
        "specs/pcb-spec.clauses.json"
    ),
    results: Annotated[
        Path, typer.Option("--results", help="The figures file to write the timing into.")
    ] = DEFAULT_RESULTS,
    label: Annotated[
        str,
        typer.Option(
            "--label",
            help="What the server was started with that it does not report, for the record.",
        ),
    ] = "",
) -> None:
    """Measure the judge's answer time, tokens and GPU memory, and record them."""
    settings = Settings()
    run_directory = run if run is not None else settings.runs_dir / category / "test"
    specification = read_clause_table(spec)
    with ChatClient(
        settings.vlm_url, settings.vlm_model, timeout_seconds=settings.vlm_timeout_seconds
    ) as client:
        try:
            timing = measure(
                run_directory,
                specification,
                client,
                images=images,
                command=["python", "-m", "spec_to_inspector.judge.timing", *sys.argv[1:]],
                server=server_facts(settings.vlm_url),
                label=label,
            )
        except (TimingError, RuntimeError) as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1) from error
    update_results(results, timing=timing)
    cold, cached = timing.cold_seconds, timing.cached_seconds
    typer.echo(
        f"{timing.images} images of {timing.category}, one question each per pass.\n"
        f"Cold:   p50 {cold.p50:.2f} s, p95 {cold.p95:.2f} s\n"
        f"Cached: p50 {cached.p50:.2f} s, p95 {cached.p95:.2f} s\n"
        f"Server memory peak: {timing.gpu.server_peak_mib} MiB "
        f"(card {timing.gpu.gpu_peak_mib} MiB)\n"
        f"Figures: {results}"
    )


if __name__ == "__main__":
    typer.run(main)
