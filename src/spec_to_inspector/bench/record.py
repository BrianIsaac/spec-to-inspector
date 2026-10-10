"""The bench's record: everything one run measured, as written to `results/stage1/bench.json`.

The file is tracked, and it is the only thing of a run that outlives the
worktree, so it holds every figure with its N and its interval, what the run
was made of (the protocol, the labelled set and the specification by their
digests; the server by what it says of itself), and one line per image, from
which any of the figures can be counted again.
"""

import hashlib
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from spec_to_inspector.bench.observe import Observation
from spec_to_inspector.bench.score import Scores
from spec_to_inspector.judge.timing import Spread

SCHEMA_VERSION: Final = 1
UNIT: Final = "U7"
SCORE_TOLERANCE: Final = 1e-3
"""Raw anomaly scores closer than this are the same score: the model repeats to about 2e-4."""

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
    return FileRef(path=path.as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


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
    """GPU memory during a stage, read from `nvidia-smi` at an interval.

    Attributes:
        process_peak_mib: The most memory the stage's own process held: the
            bench's while the anomaly model scores, the VLM server's while it
            answers; None if the process is not among the card's.
        card_peak_mib: The most memory in use on the card, by every process.
        card_before_mib: The memory in use on the card at the first reading.
        samples: How many readings were taken.
        interval_seconds: The pause between readings.
    """

    model_config = ConfigDict(frozen=True)

    process_peak_mib: int | None
    card_peak_mib: int | None
    card_before_mib: int | None
    samples: int
    interval_seconds: float


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


class JudgeSetup(BaseModel):
    """How the judge was asked.

    Attributes:
        url: The VLM server asked.
        model: The model's name on that server.
        server: What the server says of itself, where it does.
        image_min_tokens: The fewest tokens the server gives an image: the
            flag's value, `the model's own minimum` when the flag is absent,
            `unknown` when the server's command line cannot be read.
        gpu: The card's name, where `nvidia-smi` gives it.
        cache_prompt: The per-request prompt-cache switch; false is cold.
        max_regions: The most areas per image put to the judge.
        corrections: What stood in the prompts' corrections slot.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    model: str
    server: dict[str, str]
    image_min_tokens: str
    gpu: str | None
    cache_prompt: Literal[False] = False
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


class BenchRecord(BaseModel):
    """One run of the bench.

    Attributes:
        schema_version: The version of this record's layout.
        unit: The Stage I unit that writes it.
        measured_at: When the run ended, in UTC, ISO 8601.
        measured_on: The same moment as a local date.
        command: The command line.
        parts: The parts run.
        limit: The cut on each part's images, for a trial run; None for the
            whole set.
        partial: Whether the run covers less than the whole labelled set. A
            partial run's figures are not the protocol's.
        protocol: The protocol the figures follow.
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
        repeat: The comparison with the run before, where there was one of
            the same making.
        notes: What the fields mean.
        observations: One line per image run.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = SCHEMA_VERSION
    unit: str = UNIT
    measured_at: str
    measured_on: str
    command: list[str]
    parts: list[str]
    limit: int | None
    partial: bool
    protocol: FileRef
    labels: LabelledSet
    specification: SpecificationStage
    judge: JudgeSetup
    runs: dict[str, PartRun]
    scores: Scores
    times: StageTimes
    judge_memory: StageMemory
    inspector: InspectorMinutes
    leak: Leak
    repeat: Repeat | None = None
    notes: dict[str, str] = Field(default_factory=lambda: dict(NOTES))
    observations: list[Observation]


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
        ("the protocol", record.protocol.sha256, other.protocol.sha256),
        ("the labelled set", record.labels.file.sha256, other.labels.file.sha256),
        ("the specification", record.specification.pdf.sha256, other.specification.pdf.sha256),
        ("the judge's model", record.judge.model, other.judge.model),
        ("the server's model file", record.judge.server, other.judge.server),
        ("the image token minimum", record.judge.image_min_tokens, other.judge.image_min_tokens),
        ("the areas per image", record.judge.max_regions, other.judge.max_regions),
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
    )
