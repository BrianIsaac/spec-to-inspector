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
"""

import hashlib
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final, Literal, cast

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
REQUIRED_SERVER_FACTS: Final = ("image", "image_digest", "vllm_version", "dtype")

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
}


def notes_for(stage: Stage, protocol: Sequence["FileRef"]) -> dict[str, str]:
    """Write what a record's fields mean, in the words true of the run that wrote it.

    Args:
        stage: The stage the run follows.
        protocol: The protocol's files in force, the protocol's own first.

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
    return {**NOTES, **protocol_notes, **STAGE_II_NOTES}


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
            itself and, in a container, what the container says.
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
        corrections: What stood in the prompts' corrections slot.
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
    corrections: Literal["none recalled"] = "none recalled"


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
    """The proof that no correction reached a prompt.

    Attributes:
        decisions: Decisions the run made, one per image.
        with_corrections_in_prompt: Of those, decisions with a correction in
            any prompt. A run is written only when this is zero.
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
        leak: The proof that no correction reached a prompt.
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
            asks of a final run, in words; empty if it lacks nothing.
        repeat: The comparison with the run before, where there was one of
            the same making.
        notes: What the fields mean.
        observations: One line per image run.
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


def missing_for_final(record: BenchRecord) -> list[str]:
    """Say what a Stage II run's record lacks of what the protocol asks of a final run.

    The list is of what the record must hold. That three runs were made, and that no void rule was
    met, are the protocol's other conditions: a run that met a void rule writes no record.

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
    if record.digit_reasons is not None:
        missing.append("the final setting: this is the designators comparison")
    return missing


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
        ("the server", record.judge.server, other.judge.server),
        ("the image token minimum", record.judge.image_min_tokens, other.judge.image_min_tokens),
        ("the areas per image", record.judge.max_regions, other.judge.max_regions),
        ("the reason's pattern", record.judge.reason_pattern, other.judge.reason_pattern),
        (
            "the checkpoints",
            {part: run.checkpoint and run.checkpoint.sha256 for part, run in record.runs.items()},
            {part: run.checkpoint and run.checkpoint.sha256 for part, run in other.runs.items()},
        ),
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
