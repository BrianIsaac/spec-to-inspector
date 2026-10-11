"""What the bench keeps of one judged image: the facts the protocol's figures are counted from.

A decision holds everything a reject card shows; the scorer needs a few
fields of it, and the tracked results file should hold exactly those for
every image, so that any figure can be counted again from the file alone.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.bench.labels import region1_types
from spec_to_inspector.judge.decision import Cause, Decision, RegionDecision
from spec_to_inspector.judge.disposition import Outcome


class Citation(StrEnum):
    """Whether an image has a citation on region 1, and if not, why not."""

    CITED = "cited"
    NO_CLAUSE = "no clause applies"
    NO_ANSWER = "no valid answer"
    NOT_ASKED = "not asked"
    NOT_FLAGGED = "not flagged"


class Area(BaseModel):
    """One flagged area that was put before the judge, or could not be.

    Attributes:
        index: The area's rank by anomaly score, from 1.
        outcome: Accept, reject or needs review.
        review_cause: Why it is referred; None unless it is.
        asked: Whether the judge was asked about it.
        seconds: The wall time of the VLM's requests for it; None if not asked.
        attempts: Requests sent for it.
        prompt_tokens: Tokens in the last request's prompt, images included.
        completion_tokens: Tokens the last request generated.
        tokens_per_second: The server's generation rate, where it says.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    outcome: Outcome
    review_cause: Cause | None = None
    asked: bool
    seconds: float | None = None
    attempts: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tokens_per_second: float | None = None


class Observation(BaseModel):
    """One image of a bench run, as the scorer needs it.

    Attributes:
        part: The part.
        image_id: The image's id in the run.
        label: VisA's ground truth for the image.
        score: The anomaly model's raw image score.
        flagged: Whether the anomaly model flagged an area on the image.
        regions_found: How many areas it flagged.
        region1_types: The VisA defect types under region 1 in this run;
            None when there is no region or the image has no mask.
        citation: Whether there is a citation on region 1, or why not.
        cited_heading: The heading id the judge cited on region 1.
        cited_class: The defect class the judge named on region 1.
        sentence: The judge's own line about region 1.
        row_id: The row of the clause table code applied to region 1.
        outcome: The board's outcome.
        review_cause: Why the board is referred; None unless it is.
        areas: The areas put before the judge, in rank order.
        corrections_in_prompt: Whether any correction stood in any prompt of
            the image; the protocol requires false.
        judge_seconds: The wall time of judging the image: measuring and
            drawing its areas, the VLM's answers, and writing the decision.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    label: Literal["good", "bad"]
    score: float
    flagged: bool
    regions_found: int
    region1_types: tuple[str, ...] | None
    citation: Citation
    cited_heading: str | None = None
    cited_class: str | None = None
    sentence: str | None = None
    row_id: str | None = None
    outcome: Outcome
    review_cause: Cause | None = None
    areas: tuple[Area, ...] = ()
    corrections_in_prompt: bool
    judge_seconds: float

    @property
    def key(self) -> tuple[str, str]:
        """The part and the image id, which together name the image."""
        return (self.part, self.image_id)

    @property
    def vlm_seconds(self) -> float:
        """The wall time of every VLM request made for the image."""
        return sum(area.seconds or 0.0 for area in self.areas)


def _area(region: RegionDecision) -> Area:
    """Keep what the figures need of one region's decision.

    Args:
        region: The region's decision.

    Returns:
        The area.
    """
    call = region.call
    return Area(
        index=region.index,
        outcome=region.outcome,
        review_cause=region.review_cause,
        asked=call is not None,
        seconds=None if call is None else call.seconds,
        attempts=0 if call is None else call.attempts,
        prompt_tokens=None if call is None else call.prompt_tokens,
        completion_tokens=None if call is None else call.completion_tokens,
        tokens_per_second=None if call is None else call.tokens_per_second,
    )


def _citation(first: RegionDecision | None) -> Citation:
    """Say whether region 1's decision holds a citation.

    Args:
        first: The decision on region 1; None for an image with no region.

    Returns:
        The citation's state.
    """
    if first is None:
        return Citation.NOT_FLAGGED
    if first.call is None:
        return Citation.NOT_ASKED
    if first.answer is None:
        return Citation.NO_ANSWER
    return Citation.CITED if first.answer.cites_a_clause else Citation.NO_CLAUSE


def observe(decision: Decision, result: ImageResult, *, judge_seconds: float) -> Observation:
    """Take from a decision and the anomaly model's sidecar what the figures are counted from.

    Args:
        decision: The image's decision.
        result: The anomaly model's sidecar for the same image.
        judge_seconds: The wall time judging the image took.

    Returns:
        The observation.

    Raises:
        ValueError: If the image has no ground-truth label, or the first
            region judged is not the anomaly model's region 1.
    """
    if result.label is None:
        msg = f"{result.category} {result.image_id} has no ground-truth label to score against"
        raise ValueError(msg)
    first = decision.regions[0] if decision.regions else None
    if first is not None and first.index != result.regions[0].index:
        msg = (
            f"{result.category} {result.image_id}: the first area judged is region "
            f"{first.index}, not the most anomalous one"
        )
        raise ValueError(msg)
    answer = None if first is None else first.answer
    return Observation(
        part=result.category,
        image_id=result.image_id,
        label=result.label,
        score=result.score,
        flagged=bool(result.regions),
        regions_found=len(result.regions),
        region1_types=region1_types(result) if result.ground_truth_mask is not None else None,
        citation=_citation(first),
        cited_heading=None if answer is None else answer.clause_id,
        cited_class=None if answer is None else answer.defect_class,
        sentence=None if answer is None else answer.reason,
        row_id=None if first is None or first.clause is None else first.clause.id,
        outcome=decision.outcome,
        review_cause=decision.review_cause,
        areas=tuple(_area(region) for region in decision.regions),
        corrections_in_prompt=decision.corrected.in_prompt
        or any(region.corrections for region in decision.regions),
        judge_seconds=judge_seconds,
    )
