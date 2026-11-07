"""One part's run of the batch: `inspect` from the PDF to the reject cards, measured.

The same pipeline as the verb's other forms, in the same order: the PDF is parsed, the part's whole
test split is scored, every board is judged by `judge_run`, and the cards and the report are
written. What is added is what the whole-batch addition asks to be recorded, and that the run holds
to the final's setting as the bench's run does: the tracked clause table, the named checkpoints, an
empty corrections store, the warm-up before the judge's clock, and a server asked cold. A run that
breaks one of those raises and leaves no record, whatever raw readings and log it has taken by then.

What depends on the machine is passed in, and is the bench's: its pipeline and its probes.
"""

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.batch.memory import CardReading, CardSampler
from spec_to_inspector.batch.record import NOTES, BatchMemory, BatchRecord, board_counts
from spec_to_inspector.batch.report import CLAUSE_TABLE_NAME, write_report
from spec_to_inspector.bench.checkpoints import CheckpointError, read_checkpoint_record
from spec_to_inspector.bench.observe import Observation, observe, refused_answers_of
from spec_to_inspector.bench.record import (
    FileRef,
    InspectorMinutes,
    JudgeSetup,
    Leak,
    Stage,
    StageMemory,
    boards_on_threshold,
    file_ref,
    protocol_files,
)
from spec_to_inspector.bench.run import (
    JUDGE_PROCESS_NOTE,
    BenchPlan,
    ModelLoader,
    Parser,
    Probes,
    Scoring,
    ask_warm_up,
    image_min_tokens,
    parse_specification,
    read_cold,
    score_part,
    stage_times,
)
from spec_to_inspector.corrections.recall import JudgeOptions
from spec_to_inspector.judge.answer import REASON_PATTERNS
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.inspect import DEFAULT_MAX_REGIONS, judge_run
from spec_to_inspector.spec.schema import write_clause_table

if TYPE_CHECKING:
    # Anomalib takes about ten seconds to import, so it is loaded only where a model is.
    from spec_to_inspector.anomaly.infer import InferenceItem

STAGE_PARSE: Final = "parse"
STAGE_SCORE: Final = "score"
STAGE_WARM_UP: Final = "warm-up"
STAGE_JUDGE: Final = "judge"
STAGE_SERVER_LOG: Final = "server log"
STAGE_REPORT: Final = "report"
_REASON_RULE: Final = "no_digits"
"""What `inspect` holds the judge's reason to, which is the final's."""


class BatchError(RuntimeError):
    """The batch cannot be run as asked, or its run is void; the message says why."""


class BatchPlan(BaseModel):
    """What one part's run of the batch is made of.

    Attributes:
        part: The part.
        batch: The name of the run's directory under the part.
        pdf: The specification to parse; its tracked clause table sits beside it.
        visa_dir: The dataset directory `data fetch` wrote.
        runs_dir: The root of the run directories.
        record: Where the record goes; the raw readings and the server's log go beside it.
        stamp: The moment of the start, to keep this run's raw files from another's.
        protocol: The protocol the figures follow; recorded by its digest, with its additions.
        stage: The stage the run follows.
        checkpoints: The record of the checkpoints a Stage II run is held to.
        corrections_held: How many corrections the store holds, which must be none.
        max_regions: The most areas per image to put to the judge.
        command: The command line, for the record.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    batch: str
    pdf: Path
    visa_dir: Path
    runs_dir: Path
    record: Path
    stamp: str
    protocol: Path
    stage: Stage = "I"
    checkpoints: Path | None = None
    corrections_held: int = 0
    max_regions: int = DEFAULT_MAX_REGIONS
    command: tuple[str, ...] = ()

    @property
    def readings(self) -> Path:
        """The file holding every reading of the cards."""
        return self.record.with_name(f"{self.record.stem}.cards.{self.stamp}.csv")

    def bench_plan(self) -> BenchPlan:
        """Say the run in the bench's terms, for the bench's own stages.

        Returns:
            A plan of this one part. Its labelled set is named and never read.
        """
        return BenchPlan(
            parts=(self.part,),
            batch=self.batch,
            visa_dir=self.visa_dir,
            runs_dir=self.runs_dir,
            spec_pdf=self.pdf,
            clause_table=self.pdf.with_suffix(".clauses.json"),
            labels=self.protocol.with_name("clause_labels.csv"),
            protocol=self.protocol,
            max_regions=self.max_regions,
            command=self.command,
            stage=self.stage,
            reason_rule=_REASON_RULE,
            server_log=(
                self.record.with_name(f"{self.record.stem}.server-log.{self.stamp}.txt")
                if self.stage == "II"
                else None
            ),
            checkpoints=self.checkpoints if self.stage == "II" else None,
        )


def _judge_memory(readings: Sequence[CardReading], probes: Probes) -> StageMemory:
    """Lay the judge's stage out as the bench lays it, from the raw readings.

    Args:
        readings: Every reading of the cards.
        probes: How the machine was read.

    Returns:
        The judge's card during its stage; on one card, the only card.
    """
    during = [reading for reading in readings if reading.stage == STAGE_JUDGE]
    two_cards = probes.read_server_gpu is not None
    read = [r.judge_card_mib if two_cards else r.anomaly_card_mib for r in during]
    present = [value for value in read if value is not None]
    return StageMemory(
        process_peak_mib=None,
        card_peak_mib=max(present, default=None),
        card_before_mib=read[0] if read else None,
        samples=len(during),
        interval_seconds=probes.interval_seconds,
        source=probes.memory_source,
        card=probes.judge_card,
        process_note=JUDGE_PROCESS_NOTE if probes.server is not None else None,
    )


def _protocol_refs(plan: BatchPlan) -> list[FileRef]:
    """Name the protocol's files in force by their digests.

    Args:
        plan: The run's plan.

    Returns:
        The protocol first, then its additions.

    Raises:
        BatchError: If one cannot be read.
    """
    try:
        return [file_ref(path) for path in protocol_files(plan.protocol)]
    except OSError as error:
        raise BatchError(str(error)) from error


def _say_nothing(_line: str) -> None:
    """Take a line of progress and drop it.

    Args:
        _line: The line.
    """


def run_batch(  # noqa: PLR0915 - one run: its stages in order, and what each one leaves
    plan: BatchPlan,
    *,
    client: ChatClient,
    parse: Parser,
    models: ModelLoader,
    test_items: Callable[[Path, str], Sequence["InferenceItem"]],
    scoring: Scoring,
    probes: Probes,
    options: JudgeOptions,
    on_decision: Callable[[Decision], None] | None = None,
    say: Callable[[str], None] | None = None,
) -> tuple[BatchRecord, list[Decision]]:
    """Run one part from the PDF to the reject cards, and count what the addition asks.

    Args:
        plan: What to run.
        client: The VLM server's client.
        parse: Parses the specification's PDF.
        models: Opens the part's trained anomaly model.
        test_items: Lists the part's VisA test split as inference items.
        scoring: Scores images and writes a run.
        probes: How the machine is read; its interval is the sampling's.
        options: The corrections' share of the judge's arguments, from the store.
        on_decision: Called with each decision as it is made.
        say: Called with a line of progress now and then.

    Returns:
        The run's record, not yet written anywhere, and the decisions.

    Raises:
        BatchError: If the run cannot be made as planned, or is void; the bench's own stages raise
            its `BenchError` for the same.
    """
    began = time.perf_counter()
    tell = say or _say_nothing
    if not probes.reachable(client.url):
        msg = f"the judge at {client.url} cannot be reached: start its server first"
        raise BatchError(msg)
    if plan.corrections_held:
        msg = (
            f"the corrections store holds {plan.corrections_held} correction(s), and this run's "
            "setting is an empty store: move it aside, or run without --record"
        )
        raise BatchError(msg)
    protocol = _protocol_refs(plan)
    bench_plan = plan.bench_plan()
    named = None
    named_file: FileRef | None = None
    if bench_plan.checkpoints is not None:
        try:
            named = read_checkpoint_record(bench_plan.checkpoints)
            named_file = file_ref(bench_plan.checkpoints)
        except (CheckpointError, OSError) as error:
            raise BatchError(str(error)) from error
    reading = None if probes.server is None else probes.server.read(client.url)
    read_server = probes.read_server_gpu

    with CardSampler(
        plan.readings,
        read_anomaly=lambda: probes.read_gpu(None),
        read_judge=None if read_server is None else lambda: read_server(None),
        interval_seconds=probes.interval_seconds,
        stage=STAGE_PARSE,
    ) as sampler:
        specification, parsed = parse_specification(bench_plan, parse)
        if plan.part not in specification.categories():
            msg = (
                f"the specification has no clause for part {plan.part}; its parts are "
                f"{', '.join(specification.categories())}"
            )
            raise BatchError(msg)
        tell(f"Parsed {plan.pdf} in {parsed.parse_seconds:.1f} s: {parsed.clauses} clauses")

        sampler.enter(STAGE_SCORE)
        scored = score_part(
            bench_plan,
            plan.part,
            models=models,
            items=test_items(plan.visa_dir, plan.part),
            scoring=scoring,
            probes=probes,
            named=named,
        )
        tell(
            f"Scored {scored.run.images} images in {scored.run.inference_seconds:.1f} s into "
            f"{scored.directory}"
        )
        clause_table_path = scored.directory / CLAUSE_TABLE_NAME
        write_clause_table(specification, clause_table_path)
        clause_table = file_ref(clause_table_path)

        since = datetime.now(UTC)
        before = None if probes.server is None else probes.server.counters(client.url)
        sampler.enter(STAGE_WARM_UP)
        warm_up = (
            ask_warm_up(bench_plan, {plan.part: scored}, specification, client)
            if plan.stage == "II"
            else None
        )

        sampler.enter(STAGE_JUDGE)
        observations: list[Observation] = []
        started = time.perf_counter()
        last = started

        def judged(decision: Decision) -> None:
            nonlocal last
            seconds = time.perf_counter() - last
            unasked = next(
                (r for r in decision.regions if r.review_cause is Cause.SERVER_UNAVAILABLE), None
            )
            if unasked is not None:
                msg = (
                    f"the judge at {client.url} could not be asked about {plan.part} "
                    f"{decision.image_id}: {unasked.reason}. The run is void and no record is "
                    "written"
                )
                raise BatchError(msg)
            observation = observe(
                decision, scored.results[decision.image_id], judge_seconds=seconds
            )
            if observation.corrections_in_prompt:
                msg = (
                    f"a correction stood in a prompt of {plan.part} {decision.image_id}: the run "
                    "is void and no record is written"
                )
                raise BatchError(msg)
            observations.append(observation)
            if on_decision is not None:
                on_decision(decision)
            last = time.perf_counter()

        decisions = judge_run(
            scored.directory,
            specification,
            client,
            max_regions=plan.max_regions,
            cache_prompt=False,
            on_decision=judged,
            **options,
        )
        judge_seconds = time.perf_counter() - started

        sampler.enter(STAGE_SERVER_LOG)
        cold = (
            None
            if probes.server is None or reading is None
            else read_cold(
                bench_plan, reading, probes.server, client.url, before=before, since=since
            )
        )

        sampler.enter(STAGE_REPORT)
        report_began = time.perf_counter()
        report = write_report(scored.directory)
        report_seconds = time.perf_counter() - report_began

    runs = {plan.part: scored.run}
    fit = scored.run.fit_seconds
    now = datetime.now(UTC)
    record = BatchRecord(
        stage=plan.stage,
        measured_at=now.isoformat(timespec="seconds"),
        command=list(plan.command),
        part=plan.part,
        protocol=protocol,
        specification=parsed,
        clause_table=clause_table,
        judge=JudgeSetup(
            url=client.url,
            model=client.model,
            server=probes.server_facts(client.url) if reading is None else reading.facts,
            server_sources={} if reading is None else reading.sources,
            image_min_tokens=(
                image_min_tokens(probes.server_arguments(probes.server_pid(client.url)))
                if reading is None
                else reading.image_min_tokens
            ),
            gpu=probes.gpu_name(),
            cold=cold,
            warm_up=warm_up,
            reason_pattern=REASON_PATTERNS[_REASON_RULE],
            max_regions=plan.max_regions,
        ),
        run=scored.run,
        times=stage_times(parsed.parse_seconds, runs, observations, judge_seconds),
        inspector=InspectorMinutes(
            parse_seconds=parsed.parse_seconds,
            fit_seconds={plan.part: fit},
            minutes_by_part={plan.part: (parsed.parse_seconds + fit) / 60},
            minutes_all_parts=(parsed.parse_seconds + fit) / 60,
        ),
        memory=BatchMemory(
            source=probes.memory_source,
            interval_seconds=probes.interval_seconds,
            anomaly_card=probes.anomaly_card,
            judge_card=probes.judge_card,
            readings=file_ref(plan.readings),
            by_stage=sampler.peaks(),
            whole=sampler.whole(),
        ),
        judge_memory=_judge_memory(sampler.readings, probes),
        counts=board_counts(decisions),
        report=report,
        report_seconds=report_seconds,
        whole_seconds=time.perf_counter() - began,
        leak=Leak(
            decisions=len(observations),
            with_corrections_in_prompt=sum(o.corrections_in_prompt for o in observations),
        ),
        on_threshold=boards_on_threshold(observations, {plan.part: scored.run.image_threshold}),
        checkpoints_held_to=named_file,
        refused_answers=refused_answers_of(observations),
        notes=NOTES,
        observations=observations,
    )
    return record, decisions
