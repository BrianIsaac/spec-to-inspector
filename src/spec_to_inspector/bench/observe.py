"""What the bench keeps of one judged image: the facts the protocol's figures are counted from.

A decision holds everything a reject card shows; the scorer needs a few
fields of it, and the tracked results file should hold exactly those for
every image, so that any figure can be counted again from the file alone.

The protocol's `designators` comparison also needs every reason with a digit in it, since a
capital and a digit can be followed by a unit: `R5 mm` passes both the pattern and the validation.
So a reason is listed from every answer the model gave about an area, refused ones too.
"""

import json
import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.bench.labels import region1_types
from spec_to_inspector.judge.decision import Cause, Decision, RegionDecision
from spec_to_inspector.judge.disposition import Outcome

# A bare "in" is left out: "R5 in the corner" is a designator and no size.
_FOLLOWED_BY_A_UNIT: Final = re.compile(
    r"[0-9]\s*(?:mm|cm|nm|um|\u00b5m|\u03bcm|m|inch(?:es)?|mils?|thou|microns?"
    r"|(?:milli|centi|micro)?met(?:re|er)s?)(?![A-Za-z])",
    re.IGNORECASE,
)
_REASON_IN_BROKEN_JSON: Final = re.compile(r'"reason"\s*:\s*"([^"\n]*)')


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


class DigitReason(BaseModel):
    """A reason the model wrote with a numeric character in it.

    Attributes:
        part: The part.
        image_id: The image.
        area: The area's rank, from 1.
        reason: The reason as written.
        valid: Whether it stood as the answer; false for one the validation refused.
        followed_by_a_unit: Whether a digit in it is followed by a unit of length.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    area: int
    reason: str
    valid: bool
    followed_by_a_unit: bool


class DigitReasons(BaseModel):
    """Every reason of a run with a digit in it: what the `designators` comparison must show.

    One with a unit after its digit is enough to say the pattern passes a size. None says only
    that none passed on these boards.

    Attributes:
        reasons: The reasons, board by board.
        followed_by_a_unit: How many of them have a digit followed by a unit of length.
    """

    model_config = ConfigDict(frozen=True)

    reasons: tuple[DigitReason, ...]
    followed_by_a_unit: int


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
        digit_reasons: Every reason the model wrote about the image with a
            numeric character in it.
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
    digit_reasons: tuple[DigitReason, ...] = ()

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


def _reason_in(text: str) -> str | None:
    """Find the reason in what the model wrote, which may be cut off or not be JSON at all.

    Args:
        text: The model's text.

    Returns:
        The reason, or None if the text holds none.
    """
    try:
        value: object = json.loads(text)
    except ValueError:
        found = _REASON_IN_BROKEN_JSON.search(text)
        return found.group(1).strip() if found else None
    reason = cast("dict[str, object]", value).get("reason") if isinstance(value, dict) else None
    return reason.strip() if isinstance(reason, str) else None


def _digit_reasons(part: str, image_id: str, region: RegionDecision) -> list[DigitReason]:
    """List the reasons with a numeric character the model wrote about one area.

    Args:
        part: The part.
        image_id: The image.
        region: The area's decision.

    Returns:
        One per answer that has such a reason, in the order they were given.
    """
    if region.call is None:
        return []
    stood = None if region.answer is None else region.answer.reason
    listed: list[DigitReason] = []
    for text in region.call.texts:
        reason = _reason_in(text)
        if reason is not None and any(character.isnumeric() for character in reason):
            listed.append(
                DigitReason(
                    part=part,
                    image_id=image_id,
                    area=region.index,
                    reason=reason,
                    valid=reason == stood,
                    followed_by_a_unit=_FOLLOWED_BY_A_UNIT.search(reason) is not None,
                )
            )
    return listed


def digit_reasons_of(observations: Iterable[Observation]) -> DigitReasons:
    """Gather a run's reasons with a digit in them.

    Args:
        observations: The run's images.

    Returns:
        Every such reason, and how many have a digit followed by a unit of length.
    """
    reasons = tuple(reason for seen in observations for reason in seen.digit_reasons)
    return DigitReasons(
        reasons=reasons,
        followed_by_a_unit=sum(reason.followed_by_a_unit for reason in reasons),
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
        digit_reasons=tuple(
            reason
            for region in decision.regions
            for reason in _digit_reasons(result.category, result.image_id, region)
        ),
    )
