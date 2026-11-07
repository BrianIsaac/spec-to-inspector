"""The bench's record: everything one run measured, as written where the command is told.

The file is tracked, and it is the only thing of a run that outlives the
worktree, so it holds every figure with its N and its interval, what the run
was made of (the protocol's files, the labelled set, the specification and the
checkpoints by their digests; the server by what it says of itself and what its
container says), and one line per image, from which any of the figures can be
counted again.

Stage I's run on the laptop and a Stage II run on the machine write the same
layout. What is true of only one of them, such as what the memory is read from
or where the cold comes from, is in `notes_for`. The records already written
are read as they are: a single protocol file reads as a list of one.

The server's start is the protocol's, or one of its declared comparisons, or neither, and the record
says which by the container's command line it holds: never by what a run was meant to be. A kept
record's `not_final` stands as it was written, and the page reads it with what the record shows now.

A run named a store by `--declared-store` holds it under `declared_store`, by its digest, and that
field is written only for such a run: a run with no store writes the record it always wrote.
"""

import hashlib
import re
import shlex
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final, Literal, NamedTuple, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spec_to_inspector.bench.observe import DigitReasons, Observation, RefusedAnswers
from spec_to_inspector.bench.score import Scores
from spec_to_inspector.judge.timing import Spread

Stage = Literal["I", "II"]
"""Which stage's protocol a run follows: the laptop's, or the machine's."""

SCHEMA_VERSION: Final = 2
UNIT: Final = "U7"
STAGE_II_UNIT: Final = "stage2"
SCORE_TOLERANCE: Final = 1e-3
"""Raw anomaly scores closer than this are the same score: the model repeats to about 2e-4, and
inference on another device moves one by at most 5.3e-4. It also says what sits on a threshold: the
boards there are at most 3.5e-5 from it, and the next nearest in any part is 9.5e-3 away."""
REQUIRED_SERVER_FACTS: Final = ("image", "image_digest", "vllm_version", "dtype", "command")
QUANTISATION_FACT: Final = "quantisation"
"""The fact a record from before it was read does not hold. The protocol does not ask for it, so a
final run's record need not have it; `dtype` says `float16` of FP16 and of FP8 alike."""

PROTOCOL_SERVER_SCRIPT: Final = "scripts/serve_vlm_xpu.sh"
FP8_SERVER_SCRIPT: Final = "results/stage2/comparison-fp8/serve-fp8.sh"
FP8_WEIGHTS_REVISION: Final = "9cdc6310a8cb770ce18efaf4e9935334512aee45"
_WEIGHTS: Final = "/root/.cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct"
_FP8_MODEL: Final = f"{_WEIGHTS}-FP8/snapshots/{FP8_WEIGHTS_REVISION}"
_IMAGE_SIZE: Final = re.compile(r'\{"size": \{"shortest_edge": (\d+), "longest_edge": 16777216\}\}')
_IMAGE_MINIMUM_SIZE: Final = '{"size": {"shortest_edge": 65536, "longest_edge": 16777216}}'
_IMAGE_MINIMUM_TOKENS: Final = "64"
_MODEL_FLAG: Final = "--model"
_IMAGE_SIZE_FLAG: Final = "--mm-processor-kwargs"
_CONTEXT_FLAGS: Final = ("--max-model-len", "--max-num-batched-tokens")
_CACHE_FLAGS: Final = ("--no-enable-prefix-caching", "--mm-processor-cache-gb")
_PLAIN_VARIABLES: Final = {"--port": "PORT", "--gpu-memory-util": "GPU_MEMORY_UTIL"}

PROTOCOL_SERVER_START: Final[dict[str, str]] = {
    _MODEL_FLAG: f"{_WEIGHTS}/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
    "--served-model-name": "qwen3-vl-8b-instruct",
    "--dtype": "float16",
    "--enforce-eager": "",
    "--port": "8131",
    "--host": "127.0.0.1",
    "--trust-remote-code": "",
    "--disable-sliding-window": "",
    "--gpu-memory-util": "0.9",
    "--max-model-len": "32768",
    "--max-num-batched-tokens": "32768",
    "--block-size": "64",
    "--limit-mm-per-prompt": '{"image": 2}',
    _IMAGE_SIZE_FLAG: '{"size": {"shortest_edge": 1048576, "longest_edge": 16777216}}',
    "--no-enable-prefix-caching": "",
    "--mm-processor-cache-gb": "0",
    "-tp": "1",
}
"""The flags of `scripts/serve_vlm_xpu.sh start` with nothing overridden, a flag with no value as
empty text. A test holds them to the script and to the final's record."""

_DECLARED_OVERRIDES: Final = ((_MODEL_FLAG, _FP8_MODEL), (_IMAGE_SIZE_FLAG, _IMAGE_MINIMUM_SIZE))
"""What the declared comparisons change in the server's start; `designators` changes nothing."""

NOTES: Final[dict[str, str]] = {
    "protocol": (
        "every figure is defined in eval/PROTOCOL.md, written before the run; its digest at "
        "the time of the run is under `protocol`"
    ),
    "proportions": (
        "count of n; rate, low and high are fractions of 1; low and high are the 95% Wilson "
        "score interval, z = 1.959964, no continuity correction"
    ),
    "citation": (
        "the heading id in the judge's validated answer about region 1, the most anomalous "
        "area; an image with no citation counts as wrong"
    ),
    "units": (
        "*_seconds and seconds are wall-clock seconds; *_mib is MiB as nvidia-smi reports it; "
        "minutes are seconds / 60; anomaly scores and thresholds are raw PatchCore distances"
    ),
    "percentiles": "numpy.percentile, linear interpolation between the ranked values",
    "cold": "every request was sent with cache_prompt false: the whole prompt is evaluated",
    "corrections": (
        "no correction was recalled into any prompt; `leak` counts the decisions and how many "
        "of them had a correction in a prompt, which must be none"
    ),
    "not_held_out": (
        "the anomaly model's thresholds were chosen on the same test split, and the judge's "
        "prompt was written with sight of some of its images: see eval/PROTOCOL.md"
    ),
    "inspector": (
        "parse time is measured in this run and includes loading the parser's models; fit "
        "time is the one recorded when each part's model was trained, not repeated here"
    ),
}

STAGE_II_NOTES: Final[dict[str, str]] = {
    "units": (
        "*_seconds and seconds are wall-clock seconds; *_mib is MiB as xpu-smi reports it; "
        "minutes are seconds / 60; anomaly scores and thresholds are raw PatchCore distances"
    ),
    "cold": (
        "the cold comes from the server's start: vLLM ignores the request's cache_prompt and says "
        "nothing, so the server is started with its prefix cache off; judge.cold holds the flags "
        "as its container's command line gives them, the engine's own word, and the hit rate read "
        "from its log during the run, which above 0.0% voids the run"
    ),
    "memory": (
        "the anomaly model's card and the judge's are read from xpu-smi, each stage's under "
        "`memory` with the card it read; the judge's own process stays null in its container, "
        "where xpu-smi ps does not list it, and the card stands for it, 42 MiB on an idle card"
    ),
    "warm_up": (
        "one question before the judge's clock, as judged on the first flagged image and not "
        "recorded; judge.warm_up says it was asked and how long it took, not what it answered"
    ),
    "on_threshold": (
        "the rule is a strict >, so float noise decides a board whose score sits on its threshold: "
        "those of this run's boards are under `on_threshold` and the figure is read with them known"
    ),
    "quantisation": (
        "judge.server.quantisation is the engine's own word in its line in the server's log: "
        "`None` for weights it runs unquantised, `fp8` for FP8's, under the same dtype; a record "
        "without it was written before it was read, or the line and the flag could not be read"
    ),
}

DECLARED_STORE_NOTE: Final = (
    "corrections were recalled into the prompts from the declared store only, by the product's own "
    "recall; `declared_store` holds its digest, its recall and the boards it was drawn from, which "
    "are left out of the figures and keep their lines; `leak` counts the decisions with a "
    "correction in a prompt, and a correction from any other store voids the run"
)


def notes_for(
    stage: Stage, protocol: Sequence["FileRef"], *, declared: bool = False
) -> dict[str, str]:
    """Write what a record's fields mean, in the words true of the run that wrote it.

    Args:
        stage: The stage the run follows.
        protocol: The protocol's files in force, the protocol's own first.
        declared: Whether the run recalled from a declared store.

    Returns:
        The notes.
    """
    named = protocol[0].path
    protocol_notes = {
        "protocol": (
            f"every figure is defined in {named}, written before the run; its digest at the time "
            "of the run is under `protocol`"
        ),
        "not_held_out": (
            "the anomaly model's thresholds were chosen on the same test split, and the judge's "
            f"prompt was written with sight of some of its images: see {named}"
        ),
    }
    if stage == "I":
        return {**NOTES, **protocol_notes}
    if len(protocol) > 1:
        additions = ", ".join(file.path for file in protocol[1:])
        protocol_notes["protocol"] = (
            f"every figure is defined in {named}, written before the run, with what {additions} "
            "adds to it; each file's digest at the time of the run is under `protocol`"
        )
    store_note = {"corrections": DECLARED_STORE_NOTE} if declared else {}
    return {**NOTES, **protocol_notes, **STAGE_II_NOTES, **store_note}


class FileRef(BaseModel):
    """A file a run was made of, by its content.

    Attributes:
        path: The file's path as the command was given it.
        sha256: The SHA-256 of its bytes at the time of the run.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    sha256: str


def file_ref(path: Path) -> FileRef:
    """Name a file by its path and the digest of its content.

    Args:
        path: The file.

    Returns:
        The reference.
    """
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    return FileRef(path=path.as_posix(), sha256=digest)


def protocol_files(protocol: Path) -> list[Path]:
    """List the protocol's files in force: the protocol and its dated additions.

    A protocol's additions sit beside it as `<protocol>-addition-<name>-<date>.md` and take effect
    when they are committed, before the run they first govern, so the bench reads them by their
    place and needs no change for a new one.

    Args:
        protocol: The protocol's own file.

    Returns:
        The protocol first, then its additions by name.
    """
    return [protocol, *sorted(protocol.parent.glob(f"{protocol.stem}-addition-*.md"))]


class LabelledSet(BaseModel):
    """The part of the labelled set a run scored.

    Attributes:
        file: The labelled set's file.
        images: Labelled images in the run.
        single_defect: Of those, the single-defect images: the headline's N.
        multi_defect: Of those, the multi-defect images: the lenient figure's N.
    """

    model_config = ConfigDict(frozen=True)

    file: FileRef
    images: int
    single_defect: int
    multi_defect: int


class SpecificationStage(BaseModel):
    """The specification as the run parsed it.

    Attributes:
        pdf: The PDF parsed.
        clause_table: The tracked clause table the parse was held to.
        title: The specification's title.
        pages: Pages in the PDF.
        clauses: Rows of the clause table.
        headings: Numbered headings, the judge's choices.
        parse_seconds: Wall time of reading the PDF and extracting the clause
            table, including loading the parser's models.
        equals_tracked_clause_table: Whether the parsed table is the tracked
            one; a run in which it is not stops.
    """

    model_config = ConfigDict(frozen=True)

    pdf: FileRef
    clause_table: FileRef
    title: str
    pages: int
    clauses: int
    headings: int
    parse_seconds: float
    equals_tracked_clause_table: bool


class StageMemory(BaseModel):
    """GPU memory during a stage, read at an interval from the card's own tool.

    Attributes:
        process_peak_mib: The most memory the stage's own process held: the
            bench's while the anomaly model scores, the VLM server's while it
            answers; None if the process is not among the card's.
        card_peak_mib: The most memory in use on the card, by every process.
        card_before_mib: The memory in use on the card at the first reading.
        samples: How many readings were taken.
        interval_seconds: The pause between readings.
        source: The tool read; None in a record from before it was written down.
        card: The card read, as the tool takes it.
        process_note: Why `process_peak_mib` is null, where it is known.
    """

    model_config = ConfigDict(frozen=True)

    process_peak_mib: int | None
    card_peak_mib: int | None
    card_before_mib: int | None
    samples: int
    interval_seconds: float
    source: str | None = None
    card: str | None = None
    process_note: str | None = None


class PartRun(BaseModel):
    """The anomaly model's stage for one part.

    Attributes:
        part: The part.
        run_directory: Where the run was written.
        images: Images scored.
        good: Of those, good boards.
        anomalous: Of those, anomalous boards.
        flagged_good: Good boards with a flagged area.
        flagged_anomalous: Anomalous boards with a flagged area.
        image_threshold: The raw score above which a board is flagged.
        thresholds_tuned_on_test: Whether that threshold was chosen on test images.
        batch_size: Images per forward pass.
        load_seconds: Wall time of loading the trained model.
        inference_seconds: Wall time of scoring the images and writing their
            maps, masks, regions and crops.
        seconds_per_image: `inference_seconds` over `images`.
        model_trained_at: When the model was trained, in UTC.
        fit_seconds: The fit time recorded when it was trained.
        train_peak_allocated_mib: The peak GPU memory PyTorch had allocated
            in that training, as recorded then.
        memory: GPU memory while the images were scored; the process is the
            bench's own.
        checkpoint: The model's checkpoint by its digest; None in a record from
            before it was written down.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    run_directory: str
    images: int
    good: int
    anomalous: int
    flagged_good: int
    flagged_anomalous: int
    image_threshold: float
    thresholds_tuned_on_test: bool
    batch_size: int
    load_seconds: float
    inference_seconds: float
    seconds_per_image: float
    model_trained_at: str
    fit_seconds: float
    train_peak_allocated_mib: float | None
    memory: StageMemory
    checkpoint: FileRef | None = None


class ColdStart(BaseModel):
    """That every question was asked cold because of how the server was started.

    Attributes:
        server_flags: The switches keeping the prefix cache off, as the server's
            command line holds them.
        engine_prefix_caching: Whether the engine's own line in the log says its
            prefix cache is on; None if the line could not be read.
        server_started_at: When the server's container started.
        prefix_cache_hits: Tokens the server found in its prefix cache during
            the run; None if its counters could not be read.
        prefix_cache_queries: Tokens it looked for there during the run: none
            with the cache off, so the counters alone give no rate.
        hit_rate_percent: The highest hit rate its log printed during the run;
            None if it printed none or the log could not be read.
        hit_rate_readings: How many hit rates the log printed during the run.
        server_log: The log of the run, kept beside the record.
    """

    model_config = ConfigDict(frozen=True)

    server_flags: tuple[str, ...]
    engine_prefix_caching: bool | None
    server_started_at: str | None
    prefix_cache_hits: int | None
    prefix_cache_queries: int | None
    hit_rate_percent: float | None
    hit_rate_readings: int
    server_log: FileRef | None


class WarmUp(BaseModel):
    """The one question asked before the judge's clock; its answer is not recorded.

    Attributes:
        asked: Whether it was asked; a run that flags nothing has nothing to ask about.
        image: The board it was asked about.
        seconds: How long it took, which is why it is asked.
    """

    model_config = ConfigDict(frozen=True)

    asked: bool
    image: str | None = None
    seconds: float | None = None


class BoardOnThreshold(BaseModel):
    """A board whose anomaly score sits on its threshold, so that float noise decides it.

    Attributes:
        part: The part.
        image_id: The board.
        label: VisA's ground truth for it.
        score: The anomaly model's raw score.
        threshold: The part's image threshold.
        above: Whether the score is strictly above the threshold, which is the rule.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    label: Literal["good", "bad"]
    score: float
    threshold: float
    above: bool


BOARDS_NOT_SCORED_BY_THE_BENCH: Final = (
    BoardOnThreshold(
        part="pcb2",
        image_id="bad-060",
        label="bad",
        score=29.304889678955078,
        threshold=29.304889678955078,
        above=False,
    ),
    BoardOnThreshold(
        part="pcb3",
        image_id="bad-097",
        label="bad",
        score=31.543020248413086,
        threshold=31.54305076599121,
        above=False,
    ),
)
"""The owner's ruling names four boards on the threshold, and the bench scores only the two parts of
the labelled set. These are the other two, as week 2's first training on the machine measured them:
`results/stage2/week2/boards.csv` and `run-1/anomaly.json`, which a test holds them to."""


class OnThreshold(BaseModel):
    """The boards whose scores sit on their thresholds.

    Attributes:
        tolerance: How near a score must be to count as on its threshold.
        parts: The parts this run scored, which are the only ones it measured.
        boards: The boards of those parts, as this run scored them.
        elsewhere: Boards on the threshold in parts the bench does not score, from week 2's
            record; this run did not measure them.
    """

    model_config = ConfigDict(frozen=True)

    tolerance: float
    parts: tuple[str, ...]
    boards: tuple[BoardOnThreshold, ...]
    elsewhere: tuple[BoardOnThreshold, ...] = ()


class JudgeSetup(BaseModel):
    """How the judge was asked.

    Attributes:
        url: The VLM server asked.
        model: The model's name on that server.
        server: Which server answered, each fact as text: what it says of
            itself and, in a container, what the container says. `quantisation`
            is the text `None` where the engine says so; left out, it is not
            recorded.
        server_sources: Where each of those facts was read from; empty in a
            record from before it was written down.
        image_min_tokens: The fewest tokens the server gives an image: the
            flag's value, `the model's own minimum` when the flag is absent,
            `unknown` when the server's command line cannot be read.
        gpu: The card's name, where the card's own tool gives it.
        cache_prompt: The per-request prompt-cache switch, llama.cpp's; false
            is cold there, and vLLM ignores it.
        cold: Where the cold came from, on a server started cold.
        warm_up: The question asked before the judge's clock, where one is.
        reason_pattern: The reason's pattern in the schema sent.
        max_regions: The most areas per image put to the judge.
        corrections: What stood in the prompts' corrections slot: nothing, or the lines the
            declared store gives.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    model: str
    server: dict[str, str]
    server_sources: dict[str, str] = Field(default_factory=dict)
    image_min_tokens: str
    gpu: str | None
    cache_prompt: Literal[False] = False
    cold: ColdStart | None = None
    warm_up: WarmUp | None = None
    reason_pattern: str | None = None
    max_regions: int
    corrections: Literal["none recalled", "from the declared store"] = "none recalled"


class DeclaredStore(BaseModel):
    """The store a run of the corrections comparison recalled from.

    Attributes:
        file: The store's file, by its digest at the start of the run. A run in which it changed is
            void.
        strategy: When the corrections were put before the judge: the settings' own.
        limit: The most corrections that stand in one prompt.
        corrections: Rows the store holds.
        excluded: Each part's boards the store was drawn from, in the draw's order: every one is
            left out of the figures, whether or not it holds a correction.
        recalled: Each part's lines, as they stood in every prompt of that part, where the strategy
            recalls by part; none under recall on the answer, where they depend on it.
    """

    model_config = ConfigDict(frozen=True)

    file: FileRef
    strategy: str
    limit: int
    corrections: int
    excluded: dict[str, tuple[str, ...]]
    recalled: dict[str, tuple[str, ...]]

    @property
    def excluded_keys(self) -> frozenset[tuple[str, str]]:
        """The boards left out of the figures, as an observation names them."""
        return frozenset(
            (part, image_id) for part, boards in self.excluded.items() for image_id in boards
        )


class StageTimes(BaseModel):
    """Time per image, by stage.

    Attributes:
        parse_seconds: Parsing the specification, once per specification.
        anomaly_seconds_per_image: The anomaly model, per image, per part.
        flagged_images: Images with a flagged area, each put to the judge.
        areas_asked: Areas the judge was asked about.
        areas_per_flagged_image: The mean of areas asked per flagged image.
        measure_and_draw_seconds: Per flagged image, everything of judging it
            that is not the VLM: measuring its areas, drawing their overlays,
            the rule, writing the decision.
        vlm_seconds_per_area: The VLM's answer to one area, cold.
        vlm_seconds_per_flagged_image: The VLM's answers to one image's areas.
        flagged_image_seconds: A flagged image end to end: the anomaly
            model's share of its batch, then judging it.
        judge_stage_seconds: Wall time of judging every image of the run.
        prompt_tokens: Tokens in a prompt, images included.
        completion_tokens: Tokens in an answer.
        output_tokens_per_second: The server's generation rate.
    """

    model_config = ConfigDict(frozen=True)

    parse_seconds: float
    anomaly_seconds_per_image: dict[str, float]
    flagged_images: int
    areas_asked: int
    areas_per_flagged_image: float | None
    measure_and_draw_seconds: Spread | None
    vlm_seconds_per_area: Spread | None
    vlm_seconds_per_flagged_image: Spread | None
    flagged_image_seconds: Spread | None
    judge_stage_seconds: float
    prompt_tokens: Spread | None
    completion_tokens: Spread | None
    output_tokens_per_second: Spread | None


class InspectorMinutes(BaseModel):
    """Minutes from a specification to a working inspector.

    Attributes:
        parse_seconds: Parsing the specification, measured in this run.
        fit_seconds: Training each part's anomaly model, as recorded when it
            was trained.
        minutes_by_part: Parse plus one part's fit, in minutes.
        minutes_all_parts: Parse plus every part's fit one after another.
    """

    model_config = ConfigDict(frozen=True)

    parse_seconds: float
    fit_seconds: dict[str, float]
    minutes_by_part: dict[str, float]
    minutes_all_parts: float


class Leak(BaseModel):
    """How many decisions had a correction in a prompt: the proof that none did, on a final run.

    Attributes:
        decisions: Decisions the run made, one per image.
        with_corrections_in_prompt: Of those, decisions with a correction in
            any prompt. A run with no declared store is written only when this
            is zero; on one with a store, it is the boards the judge was asked about.
    """

    model_config = ConfigDict(frozen=True)

    decisions: int
    with_corrections_in_prompt: int


class Repeat(BaseModel):
    """How a run compares with the run of the same command before it.

    Attributes:
        previous_measured_at: When the earlier run was made.
        images_compared: Images both runs hold.
        flag_differs: Images flagged in one run and not in the other.
        score_differs: Images whose anomaly score differs by more than the
            tolerance.
        areas_compared: Images both runs put to the judge on region 1.
        heading_differs: Of those, images whose cited heading differs.
        class_differs: Of those, images whose named class differs.
        sentence_differs: Of those, images whose sentence differs.
        outcome_differs: Images whose board outcome differs.
        differing_images: The images counted in any line above but the sentence's.
        figures_equal: Whether every counted figure of the protocol is equal.
        previous_scores: The earlier run's figures, kept when they are not.
        previous_digit_reasons: The earlier run's reasons with a digit, which
            the `designators` comparison reports for both runs.
    """

    model_config = ConfigDict(frozen=True)

    previous_measured_at: str
    images_compared: int
    flag_differs: int
    score_differs: int
    areas_compared: int
    heading_differs: int
    class_differs: int
    sentence_differs: int
    outcome_differs: int
    differing_images: list[str]
    figures_equal: bool
    previous_scores: Scores | None = None
    previous_digit_reasons: DigitReasons | None = None


class BenchRecord(BaseModel):
    """One run of the bench.

    Attributes:
        schema_version: The version of this record's layout.
        unit: What writes it: Stage I's unit, or `stage2`.
        stage: The stage whose protocol the run follows; Stage I in a record
            from before it was written down.
        measured_at: When the run ended, in UTC, ISO 8601.
        measured_on: The same moment as a local date.
        command: The command line.
        parts: The parts run.
        limit: The cut on each part's images, for a trial run; None for the
            whole set.
        partial: Whether the run covers less than the whole labelled set. A
            partial run's figures are not the protocol's.
        protocol: The protocol's files in force, by their digests: the protocol
            the figures follow, then its dated additions.
        labels: The labelled set scored.
        specification: The specification stage.
        judge: How the judge was asked.
        runs: The anomaly model's stage, per part.
        scores: Every counted figure of the protocol.
        times: Time per image, by stage.
        judge_memory: GPU memory while the judge answered; the process is the
            VLM server's.
        inspector: Minutes from a specification to a working inspector.
        leak: How many decisions had a correction in a prompt.
        on_threshold: The boards whose scores sit on their thresholds; None in
            a record from before they were written down.
        checkpoints_held_to: The record of the named checkpoints each part's
            was held to; None for a run held to none, which is Stage I's, and in
            a record from before they were.
        digit_reasons: Every reason with a digit in it, under the `designators`
            comparison; None under any other rule.
        refused_answers: Every answer of a Stage II run the validation refused,
            by kind; None in Stage I's record, and in one from before it was
            written down.
        not_final: What this run's record lacks of what the Stage II protocol
            asks of a final run, in words, as it was written with the run; empty
            if it lacked nothing. `still_not_final` adds what is now known.
        repeat: The comparison with the run before, where there was one of
            the same making.
        notes: What the fields mean.
        observations: One line per image run.
        declared_store: The store the run recalled from, where one was named; not written
            otherwise.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1, 2] = SCHEMA_VERSION
    unit: str = UNIT
    stage: Stage = "I"
    measured_at: str
    measured_on: str
    command: list[str]
    parts: list[str]
    limit: int | None
    partial: bool
    protocol: list[FileRef]
    labels: LabelledSet
    specification: SpecificationStage
    judge: JudgeSetup
    runs: dict[str, PartRun]
    scores: Scores
    times: StageTimes
    judge_memory: StageMemory
    inspector: InspectorMinutes
    leak: Leak
    on_threshold: OnThreshold | None = None
    checkpoints_held_to: FileRef | None = None
    digit_reasons: DigitReasons | None = None
    refused_answers: RefusedAnswers | None = None
    not_final: list[str] = Field(default_factory=list)
    repeat: Repeat | None = None
    notes: dict[str, str] = Field(default_factory=lambda: dict(NOTES))
    observations: list[Observation]
    declared_store: DeclaredStore | None = Field(default=None, exclude_if=lambda held: held is None)

    @field_validator("protocol", mode="before")
    @classmethod
    def _a_list_of_files(cls, value: object) -> object:
        """Read a record written when the protocol was one file as a list of one.

        Args:
            value: The field as the file holds it.

        Returns:
            The list.
        """
        return [cast("object", value)] if isinstance(value, dict) else value


def boards_on_threshold(
    observations: Iterable[Observation],
    thresholds: dict[str, float],
    *,
    elsewhere: tuple[BoardOnThreshold, ...] = (),
) -> OnThreshold:
    """Name the boards whose scores sit on their thresholds.

    Args:
        observations: The run's images.
        thresholds: Each part's image threshold.
        elsewhere: Such boards of parts the run cannot score, to name beside its own.

    Returns:
        The boards, the run's in its order.
    """
    return OnThreshold(
        tolerance=SCORE_TOLERANCE,
        parts=tuple(thresholds),
        boards=tuple(
            BoardOnThreshold(
                part=seen.part,
                image_id=seen.image_id,
                label=seen.label,
                score=seen.score,
                threshold=thresholds[seen.part],
                above=seen.score > thresholds[seen.part],
            )
            for seen in observations
            if abs(seen.score - thresholds[seen.part]) <= SCORE_TOLERANCE
        ),
        elsewhere=elsewhere,
    )


class ServerOverride(NamedTuple):
    """A flag of the server's start that is not as the protocol has it.

    Attributes:
        flag: The flag.
        here: Its value on this run's command line; empty for a flag with none, None if absent.
        protocol: Its value in the protocol's start; the same two meanings.
    """

    flag: str
    here: str | None
    protocol: str | None


class ServerStart(NamedTuple):
    """How a run's server was started, as far as its command line says.

    Attributes:
        script: The script that writes that command line; None if none does.
        variables: The variables to set for that script, each as `NAME=value`.
        overrides: Every flag that differs from the protocol's start; none for the protocol's.
    """

    script: str | None
    variables: tuple[str, ...]
    overrides: tuple[ServerOverride, ...]


def server_flags(command: str) -> dict[str, str] | None:
    """Read the flags of `vllm serve` from a container's command line.

    Args:
        command: The command line, as the record's `judge.server.command` holds it.

    Returns:
        Each flag with its value, empty for one with none; None if it does not run `vllm serve` or
        cannot be split.
    """
    _, found, arguments = command.rpartition("vllm serve ")
    if not found:
        return None
    try:
        tokens = shlex.split(arguments)
    except ValueError:
        return None
    flags: dict[str, str] = {}
    waiting: str | None = None
    for token in tokens:
        if token.startswith("-"):
            flag, _, value = token.partition("=")
            flags[flag] = value
            waiting = None if value else flag
        elif waiting is not None:
            flags[waiting] = token
            waiting = None
    return flags


def _script_variable(override: ServerOverride, flags: dict[str, str]) -> str | None:
    """Name the script's variable that writes a flag this way.

    Args:
        override: The flag that differs.
        flags: Every flag of the command line.

    Returns:
        The variable as `NAME=value`, or None if no variable of the script writes this.
    """
    flag, here, _ = override
    if flag in _CACHE_FLAGS:
        return "PREFIX_CACHE=on" if not any(name in flags for name in _CACHE_FLAGS) else None
    if here is None:
        return None
    if flag in _PLAIN_VARIABLES:
        return f"{_PLAIN_VARIABLES[flag]}={here}"
    if flag in _CONTEXT_FLAGS:
        return f"MAX_MODEL_LEN={here}" if len({flags.get(n) for n in _CONTEXT_FLAGS}) == 1 else None
    size = _IMAGE_SIZE.fullmatch(here) if flag == _IMAGE_SIZE_FLAG else None
    return f"IMAGE_MIN_PIXELS={size.group(1)}" if size else None


def server_start(record: BenchRecord) -> ServerStart | None:
    """Say how a run's server was started, from the command line its record holds.

    Args:
        record: The run's record.

    Returns:
        The start; None if the record holds no command line that can be read, of which nothing can
        be said either way.
    """
    flags = server_flags(record.judge.server.get("command", ""))
    if flags is None:
        return None
    overrides = tuple(
        ServerOverride(flag, flags.get(flag), PROTOCOL_SERVER_START.get(flag))
        for flag in dict.fromkeys([*PROTOCOL_SERVER_START, *flags])
        if flags.get(flag) != PROTOCOL_SERVER_START.get(flag)
    )
    script = PROTOCOL_SERVER_SCRIPT
    variables: dict[str, None] = {}
    for override in overrides:
        variable = _script_variable(override, flags)
        if variable is not None:
            variables[variable] = None
        elif (override.flag, override.here) == (_MODEL_FLAG, _FP8_MODEL):
            script = FP8_SERVER_SCRIPT
        else:
            return ServerStart(script=None, variables=(), overrides=overrides)
    return ServerStart(script=script, variables=tuple(variables), overrides=overrides)


def declared_comparisons(record: BenchRecord) -> list[str]:
    """Name the protocol's declared comparisons a record is a run of.

    Args:
        record: The run's record.

    Returns:
        The comparisons, by the protocol's names; empty for the final setting. A second name means
        more than one thing was changed, which the protocol does not declare.
    """
    judge = record.judge
    flags = server_flags(judge.server.get("command", "")) or {}
    names: list[str] = []
    if (
        flags.get(_MODEL_FLAG) == _FP8_MODEL
        or judge.server.get("weights_revision") == FP8_WEIGHTS_REVISION
    ):
        names.append("fp8")
    if (
        flags.get(_IMAGE_SIZE_FLAG) == _IMAGE_MINIMUM_SIZE
        or judge.image_min_tokens == _IMAGE_MINIMUM_TOKENS
    ):
        names.append("image-minimum")
    if record.digit_reasons is not None:
        names.append("designators")
    if record.declared_store is not None:
        names.append("corrections")
    return names


def missing_for_final(record: BenchRecord) -> list[str]:
    """Say what a Stage II run's record lacks of what the protocol asks of a final run.

    The list is of what the record must hold. That three runs were made, and that no void rule was
    met, are the protocol's other conditions: a run that met a void rule writes no record. A run of
    a declared comparison, or of any other start than the protocol's, is never a final run's.

    Args:
        record: The run's record.

    Returns:
        What it lacks, in words; empty if it lacks nothing.
    """
    judge = record.judge
    missing = ["the whole labelled set: this is a partial run"] if record.partial else []
    missing += [
        f"the memory of figure 9 while {part} was scored"
        for part, run in record.runs.items()
        if run.memory.card_peak_mib is None
    ]
    if record.judge_memory.card_peak_mib is None:
        missing.append("the memory of figure 9 while the judge answered")
    missing += [
        f"which server answered: {fact}"
        for fact in REQUIRED_SERVER_FACTS
        if fact not in judge.server
    ]
    if judge.image_min_tokens == "unknown":
        missing.append("which server answered: the image's minimum tokens")
    if judge.gpu is None:
        missing.append("which server answered: the card's name")
    cold = judge.cold
    if cold is None or not cold.server_flags:
        missing.append("that the cold came from the server's start: no flag for it was read")
    if cold is None or cold.hit_rate_percent is None:
        missing.append("the prefix-cache hit rate: none was read from the server's log")
    missing += [
        f"the SHA-256 of {part}'s checkpoint"
        for part, run in record.runs.items()
        if run.checkpoint is None
    ]
    if record.checkpoints_held_to is None:
        missing.append("the checkpoints held to the digests the protocol names")
    if judge.warm_up is None or not judge.warm_up.asked:
        missing.append("the warm-up having been asked")
    missing += [
        f"the final setting: this is the {name} comparison" for name in declared_comparisons(record)
    ]
    start = server_start(record)
    missing += [
        f"the final setting: its server's `{override.flag}` is not the protocol's"
        for override in (() if start is None else start.overrides)
        if (override.flag, override.here) not in _DECLARED_OVERRIDES
    ]
    return missing


def still_not_final(record: BenchRecord) -> list[str]:
    """Say what a kept record lacks: what it was written with, and what it shows now.

    A record's `not_final` is what the code knew when it wrote the record, and the record is not
    rewritten for what the code has learned since. The rest is a matter of what the record holds.

    Args:
        record: The run's record.

    Returns:
        What it lacks, in words, the written first; empty if it lacks nothing.
    """
    return list(dict.fromkeys([*record.not_final, *missing_for_final(record)]))


def read_record(path: Path) -> BenchRecord:
    """Read a bench record.

    Args:
        path: The file `write_record` wrote.

    Returns:
        The record.

    Raises:
        ValueError: If the file is not a bench record of this layout.
        OSError: If it cannot be read.
    """
    return BenchRecord.model_validate_json(path.read_text(encoding="utf-8"))


def write_record(path: Path, record: BenchRecord) -> None:
    """Write a bench record as indented JSON, whole or not at all.

    Args:
        path: The file, created with its directory if absent.
        record: The record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    partial.replace(path)


def _server_compared(record: BenchRecord, other: BenchRecord) -> dict[str, str]:
    """Take a run's server facts as they compare with another run's.

    Args:
        record: The run.
        other: The run it is compared with.

    Returns:
        Its facts, without the quantisation if the other's record is from before it was read.
    """
    return {
        fact: value
        for fact, value in record.judge.server.items()
        if fact != QUANTISATION_FACT or QUANTISATION_FACT in other.judge.server
    }


def _store_digest(record: BenchRecord) -> str | None:
    """Name the store a run recalled from, by its bytes.

    Args:
        record: The run.

    Returns:
        The digest, or None for a run with no store.
    """
    return None if record.declared_store is None else record.declared_store.file.sha256


def same_making(record: BenchRecord, other: BenchRecord) -> list[str]:
    """Say why two runs are not runs of the same thing.

    Args:
        record: One run.
        other: Another.

    Returns:
        What differs between their makings, in words; empty when the second
        is a repeat of the first.
    """
    pairs: tuple[tuple[str, object, object], ...] = (
        ("the parts", record.parts, other.parts),
        ("the limit", record.limit, other.limit),
        (
            "the protocol's files",
            [file.sha256 for file in record.protocol],
            [file.sha256 for file in other.protocol],
        ),
        ("the labelled set", record.labels.file.sha256, other.labels.file.sha256),
        ("the specification", record.specification.pdf.sha256, other.specification.pdf.sha256),
        ("the judge's model", record.judge.model, other.judge.model),
        ("the server", _server_compared(record, other), _server_compared(other, record)),
        ("the image token minimum", record.judge.image_min_tokens, other.judge.image_min_tokens),
        ("the areas per image", record.judge.max_regions, other.judge.max_regions),
        ("the reason's pattern", record.judge.reason_pattern, other.judge.reason_pattern),
        (
            "the checkpoints",
            {part: run.checkpoint and run.checkpoint.sha256 for part, run in record.runs.items()},
            {part: run.checkpoint and run.checkpoint.sha256 for part, run in other.runs.items()},
        ),
        ("the declared store", _store_digest(record), _store_digest(other)),
    )
    return [
        f"{name}: {mine!r} against {theirs!r}" for name, mine, theirs in pairs if mine != theirs
    ]


def compare(previous: BenchRecord, current: BenchRecord) -> Repeat:
    """Compare a run with the run of the same command before it.

    Args:
        previous: The earlier run.
        current: The later run.

    Returns:
        How many images differ, in what, and whether the figures are equal.
    """
    before = {observation.key: observation for observation in previous.observations}
    both = [(before[o.key], o) for o in current.observations if o.key in before]
    asked = [
        (old, new) for old, new in both if old.sentence is not None and new.sentence is not None
    ]
    flag = {new.key for old, new in both if old.flagged != new.flagged}
    score = {new.key for old, new in both if abs(old.score - new.score) > SCORE_TOLERANCE}
    heading = {new.key for old, new in asked if old.cited_heading != new.cited_heading}
    named = {new.key for old, new in asked if old.cited_class != new.cited_class}
    outcome = {new.key for old, new in both if old.outcome != new.outcome}
    equal = previous.scores == current.scores
    return Repeat(
        previous_measured_at=previous.measured_at,
        images_compared=len(both),
        flag_differs=len(flag),
        score_differs=len(score),
        areas_compared=len(asked),
        heading_differs=len(heading),
        class_differs=len(named),
        sentence_differs=sum(old.sentence != new.sentence for old, new in asked),
        outcome_differs=len(outcome),
        differing_images=[
            f"{part} {image_id}"
            for part, image_id in sorted(flag | score | heading | named | outcome)
        ],
        figures_equal=equal,
        previous_scores=None if equal else previous.scores,
        previous_digit_reasons=previous.digit_reasons,
    )
