"""The batch's record: what one part's run of `inspect` measured, in the bench's own terms.

The whole-batch addition to the Stage II protocol asks for the protocol's figures 7, 8 and 9 "as
the bench records them or by the same readers", the boards by outcome, and the reject cards and the
report's size. So figures 7 and 8 are the bench's `StageTimes` and `InspectorMinutes`, counted by
the bench's functions; the anomaly model's stage is the bench's `PartRun`; and one line per image is
the bench's `Observation`, so that two runs can be compared field by field.

It holds no accuracy figure, by the addition: the final figure stands and is not re-read from a
batch, though the lines would let anyone count one.
"""

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.batch.memory import CardPeaks
from spec_to_inspector.batch.report import ReportWritten
from spec_to_inspector.bench.observe import Observation, RefusedAnswers
from spec_to_inspector.bench.record import (
    FileRef,
    InspectorMinutes,
    JudgeSetup,
    Leak,
    OnThreshold,
    PartRun,
    SpecificationStage,
    Stage,
    StageMemory,
    StageTimes,
)
from spec_to_inspector.judge.decision import Decision
from spec_to_inspector.judge.disposition import Outcome

BATCH_SCHEMA_VERSION: Final = 1
NOTES: Final[dict[str, str]] = {
    "what_it_is": (
        "one part's run of `spec-to-inspector inspect`: the specification's PDF parsed, the part's "
        "whole test split scored, every board judged, the reject cards and the report written"
    ),
    "no_accuracy": (
        "this record gives no accuracy figure: the final figure stands and is not re-read from a "
        "batch"
    ),
    "times": "`times` is the protocol's figure 7, counted by the bench's `stage_times`",
    "inspector": (
        "`inspector` is figure 8: parse time measured in this run plus the fit time recorded when "
        "the part's model was trained on the machine; training is not repeated"
    ),
    "memory": (
        "`memory` is figure 9 by stage, from readings of both cards at the interval it gives, "
        "every reading in the file it names; `run.memory` and `judge_memory` are the same stages "
        "laid out as the bench lays them. A stage shorter than the interval may have no reading"
    ),
    "whole_seconds": (
        "`whole_seconds` is this process's own, from the first check to the record; the whole "
        "run's wall clock is the wrapper's, which starts before Python does"
    ),
    "units": (
        "*_seconds and seconds are wall-clock seconds; *_mib is MiB as the card's tool reports it; "
        "minutes are seconds / 60; *_bytes are bytes, *_disk_bytes as allocated on the disk"
    ),
}


class BoardCounts(BaseModel):
    """What became of the boards.

    Attributes:
        boards: Boards judged.
        accepted: Boards accepted.
        rejected: Boards rejected.
        referred: Boards referred to an engineer.
        referred_by_cause: The referred, by the board's cause.
    """

    model_config = ConfigDict(frozen=True)

    boards: int
    accepted: int
    rejected: int
    referred: int
    referred_by_cause: dict[str, int]


class BatchMemory(BaseModel):
    """Figure 9: both cards read at an interval for the whole of the process, kept raw.

    Attributes:
        source: The tool read.
        interval_seconds: The time between one reading's start and the next's.
        anomaly_card: The card the anomaly model scores on.
        judge_card: The card the judge's server is on.
        readings: The file holding every reading.
        by_stage: Each card's peak in each stage, the stages in the order they came.
        whole: Each card's peak over every reading.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    interval_seconds: float
    anomaly_card: str | None
    judge_card: str | None
    readings: FileRef
    by_stage: dict[str, CardPeaks]
    whole: CardPeaks


class BatchRecord(BaseModel):
    """One part's run of the batch.

    Attributes:
        schema_version: The version of this record's layout.
        stage: The stage's protocol the run follows.
        measured_at: When the run ended, in UTC, ISO 8601.
        command: The command line.
        part: The part.
        protocol: The protocol's files in force, by their digests.
        specification: The specification stage, held to the tracked clause table.
        clause_table: The clause table this run parsed and judged against, as written in its run.
        judge: How the judge was asked.
        run: The anomaly model's stage.
        times: Figure 7.
        inspector: Figure 8.
        memory: Figure 9, both cards, by stage.
        judge_memory: The judge's stage laid out as the bench lays it.
        counts: The boards by outcome.
        report: The reject cards and the report written, and the disk they take.
        report_seconds: Wall time of writing them.
        whole_seconds: This process's wall time.
        leak: The proof that no correction reached a prompt.
        on_threshold: The boards whose scores sit on their thresholds.
        checkpoints_held_to: The record of the named checkpoints; None where a run is held to none.
        refused_answers: Every answer the validation refused, by kind.
        notes: What the fields mean.
        observations: One line per board.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = BATCH_SCHEMA_VERSION
    stage: Stage
    measured_at: str
    command: list[str]
    part: str
    protocol: list[FileRef]
    specification: SpecificationStage
    clause_table: FileRef
    judge: JudgeSetup
    run: PartRun
    times: StageTimes
    inspector: InspectorMinutes
    memory: BatchMemory
    judge_memory: StageMemory
    counts: BoardCounts
    report: ReportWritten
    report_seconds: float
    whole_seconds: float
    leak: Leak
    on_threshold: OnThreshold
    checkpoints_held_to: FileRef | None
    refused_answers: RefusedAnswers
    notes: dict[str, str]
    observations: list[Observation]


def board_counts(decisions: Sequence[Decision]) -> BoardCounts:
    """Count the boards by outcome.

    Args:
        decisions: One decision per board.

    Returns:
        The counts, the referred by the board's cause.
    """
    outcomes = Counter(decision.outcome for decision in decisions)
    causes = Counter(
        decision.review_cause.value
        for decision in decisions
        if decision.outcome is Outcome.NEEDS_REVIEW and decision.review_cause is not None
    )
    return BoardCounts(
        boards=len(decisions),
        accepted=outcomes[Outcome.ACCEPT],
        rejected=outcomes[Outcome.REJECT],
        referred=outcomes[Outcome.NEEDS_REVIEW],
        referred_by_cause=dict(sorted(causes.items())),
    )


def write_batch_record(path: Path, record: BatchRecord) -> None:
    """Write a record where the command was told.

    Args:
        path: The file; its directory is made if it is missing.
        record: The record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_batch_record(path: Path) -> BatchRecord:
    """Read a record back.

    Args:
        path: The file.

    Returns:
        The record.
    """
    return BatchRecord.model_validate_json(path.read_text(encoding="utf-8"))
