"""The scripted live check of the corrections loop, on the real judge and real crops.

For each pair, an image the judge got wrong and a sibling of the same defect
type on another board:

1. both are judged with an empty corrections slot: the before;
2. the engineer's override of the first is recorded, in a store of the pair's
   own, with a scripted note;
3. the sibling is judged again with that correction recalled, once under each
   strategy (by part, and on the judge's own answer): the after;
4. the pair's controls, images the judge had right, are judged the same three
   ways, to see what the correction disturbs.

Then, per part, with every override of that part's pairs in one store, the
first flagged images of the run are judged with the slot empty, by part and on
the answer: the answer time with the corrections in the prompt, the cost of
the second question, and a count of the answers that changed, for better and
for worse. Nothing is written into the run, and the store is a scratch file:
the settings' own corrections store is not touched.

Everything is recorded as it comes, whichever way it falls, in
`results/stage1/corrections.json`:

    scripts/serve_vlm.sh start
    uv run python -m spec_to_inspector.corrections.live_check
    scripts/serve_vlm.sh stop
"""

import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final, NamedTuple

import typer
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from spec_to_inspector.anomaly.ground_truth import defect_types
from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.corrections.override import OverrideError, build_override
from spec_to_inspector.corrections.recall import JudgeOptions, RecallStrategy, judge_options
from spec_to_inspector.corrections.render import render_correction
from spec_to_inspector.corrections.store import Correction, CorrectionStore
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import RESULT_NAME, judge_image, read_run_index
from spec_to_inspector.judge.timing import Spread, server_facts, spread
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

DEFAULT_RESULTS: Final = Path("results/stage1/corrections.json")
DEFAULT_TIMING_IMAGES: Final = 24
RESULTS_SCHEMA_VERSION: Final = 1

NOTES: Final = {
    "pairs": "each pair is judged with a corrections store of its own, holding one override: "
    "that of its misjudged image",
    "truth": "VisA's defect type under region 1, the most anomalous flagged area, read from the "
    "ground-truth mask; empty for a good board",
    "right": "the judge names the class and the clause the pair expects; for a good board, "
    "that no clause applies",
    "by_part": "the part's most recent corrections stand in the prompt; one question",
    "by_answer": "the judge is asked with an empty slot, and asked again with the corrections "
    "made where it gave that same answer before, if there are any; the second answer stands",
    "seconds": "wall time of the chat-completion requests for one image as the client saw them, "
    "both requests where the judge was asked twice; the server's prompt cache is on",
    "drift": "over the timing images, with every override of the part's pairs in one store; "
    "the pairs' misjudged images are left out, since their own corrections are in the slot. "
    "Indicative: one run, images in the run's order",
    "notes_are_scripted": "the engineer's notes were written for this check by the unit's "
    "author looking at the crops; no engineer was involved",
}


class LiveCheckError(RuntimeError):
    """The check cannot be run as asked; the message says why."""


class Pair(BaseModel):
    """A misjudged image and its sibling, with what an engineer would say of the first.

    Attributes:
        category: The part.
        misjudged: The image the judge gets wrong, whose override is recorded.
        sibling: Another image of the same defect type, judged before and after.
        truth: VisA's defect type under region 1 of both, which is also the
            specification's class; None when both are good boards the anomaly
            model flagged, which the engineer corrects to "no clause applies".
        note: The engineer's note, scripted.
        controls: Images the judge has right without corrections, judged
            before and after to see whether the correction disturbs them.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    misjudged: str
    sibling: str
    truth: str | None
    note: str
    controls: tuple[str, ...] = ()


DEFAULT_PAIRS: Final[tuple[Pair, ...]] = (
    Pair(
        category="pcb4",
        misjudged="bad-011",
        sibling="bad-020",
        truth="damage",
        note=(
            "The component's body is cracked open and pieces of it lie beside it: it was "
            "broken by force. A burn leaves the part whole but charred or sooty."
        ),
        controls=("bad-003", "bad-009"),
    ),
    Pair(
        category="pcb4",
        misjudged="bad-033",
        sibling="bad-026",
        truth="extra",
        note=(
            "A loose black part lies across pads where the board has no component of its own: "
            "an extra object on the board. The black is the part's own body, not charring."
        ),
        controls=("bad-000", "bad-028"),
    ),
    Pair(
        category="pcb4",
        misjudged="bad-048",
        sibling="bad-050",
        truth="missing",
        note=(
            "The white outline holds two bare solder pads and no part between them: the "
            "component is absent. Dark specks on a bare pad are flux residue, not foreign "
            "material."
        ),
        controls=("bad-056", "bad-047"),
    ),
    Pair(
        category="pcb4",
        misjudged="bad-012",
        sibling="bad-015",
        truth="damage",
        note=(
            "The connector's metal shell is dented and bent out of shape: mechanical damage. "
            "Its surface is clean metal with nothing lying on it."
        ),
        controls=("bad-004", "bad-056"),
    ),
    Pair(
        category="pcb4",
        misjudged="good-0990",
        sibling="good-0026",
        truth=None,
        note=(
            "Nothing is wrong here: the parts are present, whole and clean, and the board is "
            "bare where it should be. The detector reacted to an ordinary difference between "
            "boards."
        ),
        controls=("bad-002", "bad-056"),
    ),
)
"""The scripted pairs, chosen from the judge's answers on the two test runs with an empty slot.

On pcb4: a damaged component called a burn; a stray part called a burn; a missing component
called foreign material; a dented connector called foreign material; and a good board the
anomaly model flagged, called foreign material. The controls are images the judge had right.
The notes were written for the check from the crops; see `NOTES`."""


class Judgement(BaseModel):
    """What the judge said of region 1 of one image, in one of the check's passes.

    Attributes:
        image_id: The image.
        label: VisA's label of the board: good or bad.
        truth: VisA's defect types under region 1; empty for a good board.
        defect_class: The class the judge named; None if it named none.
        clause_id: The numbered heading it cited; None with the class.
        judge_line: The judge's own line of description.
        outcome: What code made of the region.
        review_cause: Why it was referred, when it was.
        corrections: The corrections that stood in the prompt of this answer.
        requests: Chat-completion requests sent for the image.
        asked_twice: Whether recall on the answer brought a second question.
        first_class: The class named in the first of two questions.
        first_clause: The heading cited in the first of two questions.
        seconds: Wall time of the requests together.
        prompt_tokens: Tokens of the last request's prompt, images included.
        cached_tokens: Of those, taken from the server's cache.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    label: str
    truth: tuple[str, ...]
    defect_class: str | None
    clause_id: str | None
    judge_line: str | None
    outcome: Outcome
    review_cause: Cause | None
    corrections: tuple[str, ...]
    requests: int
    asked_twice: bool
    first_class: str | None
    first_clause: str | None
    seconds: float
    prompt_tokens: int | None
    cached_tokens: int | None

    def names(self, defect_class: str | None, clause_id: str | None) -> bool:
        """Say whether the judge named this class and this clause.

        Args:
            defect_class: The class expected; None for "no clause applies".
            clause_id: The heading expected; None with the class.

        Returns:
            True if both are what the judge answered, a valid answer having come.
        """
        answered = self.judge_line is not None
        return answered and (self.defect_class, self.clause_id) == (defect_class, clause_id)


class ControlRecord(BaseModel):
    """A control image, judged without and with the pair's correction.

    Attributes:
        before: With an empty slot.
        by_part: With the correction recalled by part.
        by_answer: With recall on the judge's own answer.
        held_by_part: Whether the answer by part is the answer before.
        held_by_answer: Whether the answer under recall on the answer is.
    """

    model_config = ConfigDict(frozen=True)

    before: Judgement
    by_part: Judgement
    by_answer: Judgement
    held_by_part: bool
    held_by_answer: bool


class PairRecord(BaseModel):
    """The before and after of one pair.

    Attributes:
        pair: The pair as scripted.
        expected_class: The class the engineer corrects to; None for no defect.
        expected_clause: Its numbered heading; None with the class.
        correction: The override as the judge is shown it; None if none was
            recorded.
        not_recorded: Why no override was recorded, when none was: the judge
            had the "misjudged" image right in this run.
        misjudged_before: The misjudged image, with an empty slot.
        sibling_before: The sibling, with an empty slot.
        sibling_by_part: The sibling with the correction recalled by part.
        sibling_by_answer: The sibling under recall on the answer.
        controls: The control images.
        right_before: Whether the sibling's answer was right with an empty slot.
        right_by_part: Whether it was right with the correction, by part.
        right_by_answer: Whether it was right under recall on the answer.
    """

    model_config = ConfigDict(frozen=True)

    pair: Pair
    expected_class: str | None
    expected_clause: str | None
    correction: str | None
    not_recorded: str | None
    misjudged_before: Judgement
    sibling_before: Judgement
    sibling_by_part: Judgement | None
    sibling_by_answer: Judgement | None
    controls: tuple[ControlRecord, ...]
    right_before: bool
    right_by_part: bool | None
    right_by_answer: bool | None


class SlotPass(BaseModel):
    """One pass over the timing images under one recall.

    Attributes:
        recall: `none` for an empty slot, else the strategy.
        corrections_in_store: Overrides in the store the pass recalled from.
        images: Images judged, one region each.
        asked_twice: Images whose answer brought a second question.
        seconds: Wall time per image, every request counted.
        prompt_tokens: Tokens of each image's last prompt, images included.
        cached_tokens: Of those, taken from the server's cache.
        judgements: The answers, in the order judged.
    """

    model_config = ConfigDict(frozen=True)

    recall: str
    corrections_in_store: int = Field(ge=0)
    images: int = Field(ge=1)
    asked_twice: int = Field(ge=0)
    seconds: Spread
    prompt_tokens: Spread | None
    cached_tokens: Spread | None
    judgements: tuple[Judgement, ...]


class Drift(BaseModel):
    """What changed between the empty slot and a recall, over the timing images.

    Scored on the images whose region 1 lies on exactly one VisA defect type
    (right is naming that type) and, apart, on the good boards the anomaly
    model flagged (cleared is saying that no clause applies).

    Attributes:
        recall: The strategy compared with the empty slot.
        scored: Anomalous images with one defect type under region 1.
        right_before: Of those, right with an empty slot.
        right_after: Of those, right with the corrections.
        wrong_to_right: Of those, wrong before and right after.
        right_to_wrong: Of those, right before and wrong after.
        answers_changed: Images of the pass, of any kind, whose class or
            clause changed.
        good_boards: Good boards among the images.
        good_cleared_before: Of those, "no clause applies" with an empty slot.
        good_cleared_after: Of those, "no clause applies" with the corrections.
    """

    model_config = ConfigDict(frozen=True)

    recall: str
    scored: int
    right_before: int
    right_after: int
    wrong_to_right: int
    right_to_wrong: int
    answers_changed: int
    good_boards: int
    good_cleared_before: int
    good_cleared_after: int


class CategoryCheck(BaseModel):
    """The check on one part.

    Attributes:
        category: The part.
        run: The run directory judged.
        pairs: The pairs, each before and after.
        slot_corrections: The lines that stood in the slot in the pass by part.
        passes: The passes over the timing images: empty slot, by part, on
            the answer.
        drift: What each recall changed against the empty slot.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    run: str
    pairs: tuple[PairRecord, ...]
    slot_corrections: tuple[str, ...]
    passes: tuple[SlotPass, ...]
    drift: tuple[Drift, ...]


class CorrectionsResults(BaseModel):
    """The figures file of the corrections loop, `results/stage1/corrections.json`.

    Attributes:
        schema_version: The version of this file's layout.
        notes: What the terms and units mean.
        measured_at: When the check ended, in UTC, ISO 8601.
        command: The command line.
        specification: The specification's title.
        judge_url: The VLM server asked.
        judge_model: The model's name on that server.
        server: What the server says of itself.
        categories: The check, part by part.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = RESULTS_SCHEMA_VERSION
    notes: dict[str, str] = Field(default_factory=lambda: dict(NOTES))
    measured_at: str
    command: list[str]
    specification: str
    judge_url: str
    judge_model: str
    server: dict[str, str]
    categories: tuple[CategoryCheck, ...]


class PairDecisions(NamedTuple):
    """The decisions behind a pair's record, for a test to hold to the judge's contract.

    Attributes:
        record: The pair's record.
        correction: The override as stored, or None if none was recorded.
        sibling_by_part: The sibling's decision with the correction, by part.
        sibling_by_answer: The sibling's decision under recall on the answer.
    """

    record: PairRecord
    correction: Correction | None
    sibling_by_part: Decision | None
    sibling_by_answer: Decision | None


def _judgement(decision: Decision, result: ImageResult) -> Judgement:
    """Take what the check records from a decision on one region.

    Args:
        decision: The image's decision, region 1 judged.
        result: The anomaly model's sidecar, for the label and the truth.

    Returns:
        The judgement.

    Raises:
        LiveCheckError: If the image has no region to judge, or the judge
            could not be reached.
    """
    if not decision.regions:
        msg = f"{decision.image_id} has no flagged area, so there is nothing to put to the judge"
        raise LiveCheckError(msg)
    region = decision.regions[0]
    if region.review_cause is Cause.SERVER_UNAVAILABLE:
        msg = f"{decision.image_id}: {region.reason}"
        raise LiveCheckError(msg)
    calls = [call for call in (region.first_call, region.call) if call is not None]
    last = calls[-1] if calls else None
    values = result.regions[0].ground_truth_values or []
    try:
        truth = tuple(defect_types(result.category, values))
    except ValueError:
        truth = ()
    return Judgement(
        image_id=decision.image_id,
        label=result.label or "",
        truth=truth,
        defect_class=None if region.answer is None else region.answer.defect_class,
        clause_id=None if region.answer is None else region.answer.clause_id,
        judge_line=None if region.answer is None else region.answer.reason,
        outcome=region.outcome,
        review_cause=region.review_cause,
        corrections=region.corrections,
        requests=sum(call.attempts for call in calls),
        asked_twice=region.first_call is not None,
        first_class=None if region.first_answer is None else region.first_answer.defect_class,
        first_clause=None if region.first_answer is None else region.first_answer.clause_id,
        seconds=sum(call.seconds for call in calls),
        prompt_tokens=None if last is None else last.prompt_tokens,
        cached_tokens=None if last is None else last.cached_tokens,
    )


class _Bench(NamedTuple):
    """What every judging of the check shares.

    Attributes:
        run: The run directory.
        specification: The parsed specification.
        client: The VLM server's client.
    """

    run: Path
    specification: Specification
    client: ChatClient

    def judge(self, image_id: str, options: JudgeOptions | None = None) -> Decision:
        """Judge region 1 of an image, leaving no file in the run.

        Args:
            image_id: The image.
            options: The corrections' callables; none for an empty slot.

        Returns:
            The decision.

        Raises:
            LiveCheckError: If the run holds no such image.
        """
        directory = self.run / image_id
        if not (directory / RESULT_NAME).is_file():
            msg = f"the run {self.run} holds no image {image_id}"
            raise LiveCheckError(msg)
        return judge_image(
            directory,
            self.specification,
            self.client,
            max_regions=1,
            write=False,
            **(options or JudgeOptions(recall=None, recall_on_answer=None, overridden=None)),
        )

    def result(self, image_id: str) -> ImageResult:
        """Read an image's sidecar.

        Args:
            image_id: The image.

        Returns:
            The anomaly model's result.

        Raises:
            LiveCheckError: If the run holds no such image.
        """
        try:
            text = (self.run / image_id / RESULT_NAME).read_text(encoding="utf-8")
        except OSError as error:
            msg = f"the run {self.run} holds no image {image_id}"
            raise LiveCheckError(msg) from error
        return ImageResult.model_validate_json(text)

    def judged(self, image_id: str, options: JudgeOptions | None = None) -> Judgement:
        """Judge region 1 of an image and take the check's record of it.

        Args:
            image_id: The image.
            options: The corrections' callables; none for an empty slot.

        Returns:
            The judgement.
        """
        return _judgement(self.judge(image_id, options), self.result(image_id))


def _expected(specification: Specification, pair: Pair) -> tuple[str | None, str | None]:
    """Give the class and the heading a pair's engineer corrects to.

    Args:
        specification: The parsed specification.
        pair: The pair.

    Returns:
        The specification's class of VisA's defect type and its numbered
        heading; None for both when the pair is of good boards.

    Raises:
        LiveCheckError: If the part has not exactly one heading for the type.
    """
    if pair.truth is None:
        return None, None
    headings = list(
        dict.fromkeys(
            clause.heading_id
            for clause in specification.clauses
            if clause.category == pair.category and clause.defect_class == pair.truth
        )
    )
    if len(headings) != 1:
        msg = (
            f"part {pair.category} has {len(headings)} clauses for the defect type "
            f"'{pair.truth}'; the check needs exactly one"
        )
        raise LiveCheckError(msg)
    return pair.truth, headings[0]


def check_pair(
    pair: Pair,
    run_directory: Path,
    specification: Specification,
    client: ChatClient,
    store: CorrectionStore,
) -> PairDecisions:
    """Judge a pair before and after its override, under both recall strategies.

    Args:
        pair: The misjudged image, its sibling and its controls.
        run_directory: The run of the pair's part.
        specification: The parsed specification.
        client: The VLM server's client.
        store: A store for this pair alone; its override is recorded there.

    Returns:
        The pair's record, with the override and the sibling's two decisions
        after it.

    Raises:
        LiveCheckError: If an image is not in the run, has no flagged area,
            or the judge cannot be reached.
    """
    bench = _Bench(run_directory, specification, client)
    expected_class, expected_clause = _expected(specification, pair)
    misjudged = bench.judge(pair.misjudged)
    misjudged_before = _judgement(misjudged, bench.result(pair.misjudged))
    sibling_before = bench.judged(pair.sibling)
    controls_before = [bench.judged(image_id) for image_id in pair.controls]

    correction: Correction | None = None
    not_recorded: str | None = None
    try:
        override = build_override(
            misjudged,
            specification,
            run_directory / pair.misjudged,
            clause_id=expected_clause,
            defect_class=expected_class,
            note=pair.note,
        )
    except OverrideError as error:
        not_recorded = str(error)
    else:
        correction = store.record(override)

    by_part: Decision | None = None
    by_answer: Decision | None = None
    controls: list[ControlRecord] = []
    if correction is not None:
        part = judge_options(store, RecallStrategy.PART)
        answer = judge_options(store, RecallStrategy.ANSWER)
        by_part = bench.judge(pair.sibling, part)
        by_answer = bench.judge(pair.sibling, answer)
        for before in controls_before:
            with_part = bench.judged(before.image_id, part)
            with_answer = bench.judged(before.image_id, answer)
            controls.append(
                ControlRecord(
                    before=before,
                    by_part=with_part,
                    by_answer=with_answer,
                    held_by_part=with_part.names(before.defect_class, before.clause_id),
                    held_by_answer=with_answer.names(before.defect_class, before.clause_id),
                )
            )
    sibling_result = bench.result(pair.sibling)
    after_part = None if by_part is None else _judgement(by_part, sibling_result)
    after_answer = None if by_answer is None else _judgement(by_answer, sibling_result)
    record = PairRecord(
        pair=pair,
        expected_class=expected_class,
        expected_clause=expected_clause,
        correction=None if correction is None else render_correction(correction),
        not_recorded=not_recorded,
        misjudged_before=misjudged_before,
        sibling_before=sibling_before,
        sibling_by_part=after_part,
        sibling_by_answer=after_answer,
        controls=tuple(controls),
        right_before=sibling_before.names(expected_class, expected_clause),
        right_by_part=(
            None if after_part is None else after_part.names(expected_class, expected_clause)
        ),
        right_by_answer=(
            None if after_answer is None else after_answer.names(expected_class, expected_clause)
        ),
    )
    return PairDecisions(record, correction, by_part, by_answer)


def _slot_pass(
    bench: _Bench,
    image_ids: Sequence[str],
    warm_up: str,
    *,
    recall: str,
    options: JudgeOptions | None,
    held: int,
) -> SlotPass:
    """Judge the timing images under one recall, after a warm-up on another image.

    Args:
        bench: The run, the specification and the client.
        image_ids: The images to judge.
        warm_up: An image judged first and not counted, so that the prefix
            the pass shares is in the server's cache.
        recall: The pass's name in the record.
        options: The corrections' callables; none for an empty slot.
        held: Overrides in the store recalled from.

    Returns:
        The pass.
    """
    bench.judge(warm_up, options)
    judgements = [bench.judged(image_id, options) for image_id in image_ids]
    prompts = [j.prompt_tokens for j in judgements if j.prompt_tokens is not None]
    cached = [j.cached_tokens for j in judgements if j.cached_tokens is not None]
    return SlotPass(
        recall=recall,
        corrections_in_store=held,
        images=len(judgements),
        asked_twice=sum(j.asked_twice for j in judgements),
        seconds=spread([j.seconds for j in judgements]),
        prompt_tokens=spread([float(value) for value in prompts]) if prompts else None,
        cached_tokens=spread([float(value) for value in cached]) if cached else None,
        judgements=tuple(judgements),
    )


def drift(before: SlotPass, after: SlotPass) -> Drift:
    """Count what a recall changed against the empty slot, image by image.

    Args:
        before: The pass with an empty slot.
        after: A pass over the same images with corrections recalled.

    Returns:
        The counts.

    Raises:
        ValueError: If the passes are not over the same images in order.
    """
    if [j.image_id for j in before.judgements] != [j.image_id for j in after.judgements]:
        msg = "the two passes are not over the same images"
        raise ValueError(msg)
    pairs = list(zip(before.judgements, after.judgements, strict=True))
    scored = [(b, a) for b, a in pairs if b.label == "bad" and len(b.truth) == 1]
    good = [(b, a) for b, a in pairs if b.label == "good"]

    def right(judgement: Judgement) -> bool:
        return judgement.defect_class == judgement.truth[0]

    def cleared(judgement: Judgement) -> bool:
        return judgement.judge_line is not None and judgement.defect_class is None

    return Drift(
        recall=after.recall,
        scored=len(scored),
        right_before=sum(right(b) for b, _ in scored),
        right_after=sum(right(a) for _, a in scored),
        wrong_to_right=sum(not right(b) and right(a) for b, a in scored),
        right_to_wrong=sum(right(b) and not right(a) for b, a in scored),
        answers_changed=sum(
            (b.defect_class, b.clause_id) != (a.defect_class, a.clause_id) for b, a in pairs
        ),
        good_boards=len(good),
        good_cleared_before=sum(cleared(b) for b, _ in good),
        good_cleared_after=sum(cleared(a) for _, a in good),
    )


def check_category(
    category: str,
    pairs: Sequence[Pair],
    run_directory: Path,
    specification: Specification,
    client: ChatClient,
    work_directory: Path,
    *,
    timing_images: int = DEFAULT_TIMING_IMAGES,
) -> CategoryCheck:
    """Run the check on one part: its pairs, then the passes over the timing images.

    Args:
        category: The part.
        pairs: The part's pairs.
        run_directory: The part's run.
        specification: The parsed specification.
        client: The VLM server's client.
        work_directory: Where the scratch stores go: one per pair, and one
            holding every override recorded, for the passes.
        timing_images: How many flagged images each pass judges.

    Returns:
        The part's check.

    Raises:
        LiveCheckError: If the run is of another part, holds too few flagged
            images, an image of a pair is not in it, or the judge cannot be
            reached.
    """
    index = read_run_index(run_directory)
    if index.category != category:
        msg = f"{run_directory} is a run of part {index.category}, not of {category}"
        raise LiveCheckError(msg)
    records: list[PairRecord] = []
    together = CorrectionStore(work_directory / f"{category}-together.sqlite3")
    for number, pair in enumerate(pairs, start=1):
        alone = CorrectionStore(work_directory / f"{category}-pair-{number}.sqlite3")
        checked = check_pair(pair, run_directory, specification, client, alone)
        records.append(checked.record)
        if checked.correction is not None:
            together.record(checked.correction)

    overridden = {pair.misjudged for pair in pairs}
    flagged = [
        entry.image_id
        for entry in index.entries
        if entry.regions > 0 and entry.image_id not in overridden
    ]
    if len(flagged) < timing_images + 1:
        msg = (
            f"the run {run_directory} has {len(flagged)} flagged images besides the pairs' "
            f"own, not the {timing_images + 1} the passes need"
        )
        raise LiveCheckError(msg)
    chosen, warm_up = flagged[:timing_images], flagged[timing_images]
    bench = _Bench(run_directory, specification, client)
    held = together.count()
    passes = [_slot_pass(bench, chosen, warm_up, recall="none", options=None, held=0)]
    if held:
        passes += [
            _slot_pass(
                bench,
                chosen,
                warm_up,
                recall=strategy.value,
                options=judge_options(together, strategy),
                held=held,
            )
            for strategy in RecallStrategy
        ]
    by_part = judge_options(together, RecallStrategy.PART)["recall"]
    return CategoryCheck(
        category=category,
        run=str(run_directory),
        pairs=tuple(records),
        slot_corrections=tuple(by_part(category)) if by_part is not None else (),
        passes=tuple(passes),
        drift=tuple(drift(passes[0], later) for later in passes[1:]),
    )


def summary_lines(results: CorrectionsResults) -> list[str]:
    """Give the check's outcome in lines for the terminal.

    Args:
        results: The figures.

    Returns:
        One line per pair, and per part the answer times and what changed.
    """

    def said(judgement: Judgement | None) -> str:
        if judgement is None:
            return "not asked"
        if judgement.defect_class is None:
            return "no clause" if judgement.judge_line is not None else "no answer"
        return f"{judgement.defect_class} {judgement.clause_id}"

    lines: list[str] = []
    for check in results.categories:
        for record in check.pairs:
            expected = (
                f"{record.expected_class} {record.expected_clause}"
                if record.expected_class is not None
                else "no clause"
            )
            lines.append(
                f"{check.category} {record.pair.misjudged} -> {record.pair.sibling} "
                f"(expected {expected}): before {said(record.sibling_before)}; "
                f"by part {said(record.sibling_by_part)}; "
                f"on the answer {said(record.sibling_by_answer)}"
                + (f" [no override: {record.not_recorded}]" if record.not_recorded else "")
            )
            lines += [
                f"  control {control.before.image_id}: before {said(control.before)}; "
                f"by part {said(control.by_part)}; on the answer {said(control.by_answer)}"
                for control in record.controls
            ]
        lines += [
            f"{check.category} answer time, {timed.recall}: p50 {timed.seconds.p50:.2f} s, "
            f"p95 {timed.seconds.p95:.2f} s over {timed.images} images"
            + (f", {timed.asked_twice} asked twice" if timed.recall == "answer" else "")
            for timed in check.passes
        ]
        lines += [
            f"{check.category} drift, {moved.recall}: {moved.right_before} of {moved.scored} "
            f"right before, {moved.right_after} after ({moved.wrong_to_right} fixed, "
            f"{moved.right_to_wrong} broken); good boards cleared "
            f"{moved.good_cleared_before} then {moved.good_cleared_after} of {moved.good_boards}"
            for moved in check.drift
        ]
    return lines


def main(
    category: Annotated[
        list[str] | None,
        typer.Option(
            "--category", "-c", help="Check only this part's pairs. May be repeated; all if absent."
        ),
    ] = None,
    pairs_file: Annotated[
        Path | None,
        typer.Option("--pairs", help="A JSON list of pairs to check instead of the scripted ones."),
    ] = None,
    images: Annotated[
        int,
        typer.Option("--images", min=2, help="Flagged images per timing pass, per part."),
    ] = DEFAULT_TIMING_IMAGES,
    spec: Annotated[Path, typer.Option("--spec", help="The specification's clause table.")] = Path(
        "specs/pcb-spec.clauses.json"
    ),
    results: Annotated[
        Path, typer.Option("--results", help="The figures file to write.")
    ] = DEFAULT_RESULTS,
) -> None:
    """Run the corrections loop's live check and record the before and after."""
    settings = Settings()
    try:
        specification = read_clause_table(spec)
        pairs = (
            DEFAULT_PAIRS
            if pairs_file is None
            else TypeAdapter(tuple[Pair, ...]).validate_json(pairs_file.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    parts = list(dict.fromkeys(pair.category for pair in pairs))
    chosen = [part for part in parts if not category or part in category]
    if not chosen:
        typer.echo(f"no pair to check; the pairs are of {', '.join(parts) or 'no part'}", err=True)
        raise typer.Exit(code=1)

    checks: list[CategoryCheck] = []
    with (
        tempfile.TemporaryDirectory(prefix="corrections-check-") as work,
        ChatClient(
            settings.vlm_url, settings.vlm_model, timeout_seconds=settings.vlm_timeout_seconds
        ) as client,
    ):
        try:
            checks = [
                check_category(
                    part,
                    [pair for pair in pairs if pair.category == part],
                    settings.runs_dir / part / "test",
                    specification,
                    client,
                    Path(work),
                    timing_images=images,
                )
                for part in chosen
            ]
        except (ValueError, RuntimeError) as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1) from error
    written = CorrectionsResults(
        measured_at=datetime.now(UTC).isoformat(timespec="seconds"),
        command=["python", "-m", "spec_to_inspector.corrections.live_check", *sys.argv[1:]],
        specification=specification.title,
        judge_url=settings.vlm_url,
        judge_model=settings.vlm_model,
        server=server_facts(settings.vlm_url),
        categories=tuple(checks),
    )
    results.parent.mkdir(parents=True, exist_ok=True)
    results.write_text(written.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for line in summary_lines(written):
        typer.echo(line)
    typer.echo(f"Figures: {results}")


if __name__ == "__main__":
    typer.run(main)
