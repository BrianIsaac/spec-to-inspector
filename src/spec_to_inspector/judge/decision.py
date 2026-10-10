"""The decision: the judge's answer and the disposition rule, composed.

The model names a defect class and the numbered heading of a clause. Code
does the rest: it finds the heading in the table of the board's own part,
picks the row for the zone the region was measured in, and hands that row,
the measurement and the class named to the disposition rule. Whatever the
rule cannot settle, and whatever the model could not be asked or did not
answer properly, is referred to an engineer with the cause in words.

No number in a decision comes from the model. The figures are the
measurement's, the clause's and the anomaly model's; the model's sentence is
kept as text, and its schema bars figures from it.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Final, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.disposition import Disposition, Outcome, dispose
from spec_to_inspector.judge.join import rule_clause
from spec_to_inspector.measure import MeasuredRegion
from spec_to_inspector.spec import schema
from spec_to_inspector.spec.schema import ANY_ZONE, Specification

DECISION_SCHEMA_VERSION: Final = 1
_ENGINEER: Final = "; an engineer must decide"


class Cause(StrEnum):
    """Why a region or a board is referred to an engineer.

    The first four are the disposition rule's own causes, by the same words;
    the rest arise around the rule.
    """

    MISSING_CLAUSE = "missing clause"
    CLASS_MISMATCH = "class mismatch"
    ZONE_MISMATCH = "zone mismatch"
    UNDEFINED_MEASUREMENT = "undefined measurement"
    NO_CLAUSE_APPLIES = "no clause applies"
    OUTSIDE_ZONES = "outside every zone"
    CLAUSE_ORDERS_REVIEW = "clause orders review"
    NOT_MEASURED = "not measured"
    MALFORMED_ANSWER = "malformed answer"
    SERVER_UNAVAILABLE = "server unavailable"
    NOT_JUDGED = "not judged"


class JudgeCall(BaseModel):
    """What asking the judge about one region cost and returned.

    Attributes:
        attempts: Requests sent: one, or two when the first answer was refused.
        seconds: Wall time of the requests together, as the client saw it.
        prompt_tokens: Tokens in the last request's prompt, images included.
        completion_tokens: Tokens the last request generated.
        cached_tokens: Prompt tokens the server took from its cache in the
            last request; None if the server does not say.
        tokens_per_second: The server's generation rate in the last request;
            None if the server does not say.
        texts: The model's text of each attempt, as written.
        error: Why no valid answer came, in words; None when one did.
    """

    model_config = ConfigDict(frozen=True)

    attempts: int = Field(ge=1)
    seconds: float = Field(ge=0.0)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    tokens_per_second: float | None = None
    texts: tuple[str, ...] = ()
    error: str | None = None


class RegionDecision(BaseModel):
    """What becomes of one flagged region, with everything the reason rests on.

    Attributes:
        index: The region's index in the anomaly model's result: its rank by
            peak score, from 1.
        outcome: Accept, reject or needs review.
        reason: One sentence, written by code; its figures are the
            measurement's and the clause's. Where a citation is refused, the
            sentence quotes the class and the clause number the model cited,
            which the answer's validation holds to letters and to a clause
            number.
        review_cause: Why an engineer must decide; None unless the outcome is
            needs review.
        from_peak: Whether the region is the anomaly model's peak-patch
            fallback, which has a place but no size of its own.
        crop: The crop the judge was shown, relative to the image's directory.
        overlay: The heatmap overlay the judge was shown, relative to the
            image's directory.
        measurement: The region as measured; None if it could not be measured.
        answer: The model's answer: its sentence, the class it named and the
            heading it cited; None if no valid answer came.
        clause: The row of the clause table that was applied, quoted whole;
            None when no row could be.
        rule: The disposition rule's own answer, with the figures compared;
            None when the rule was not reached or its figures do not apply.
        call: What asking the judge cost and returned; None if it was not asked.
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    outcome: Outcome
    reason: str = Field(min_length=1)
    review_cause: Cause | None = None
    from_peak: bool = False
    crop: str | None = None
    overlay: str | None = None
    measurement: MeasuredRegion | None = None
    answer: JudgeAnswer | None = None
    clause: schema.Clause | None = None
    rule: Disposition | None = None
    call: JudgeCall | None = None


class Decision(BaseModel):
    """What becomes of one board image, written beside its inference as `decision.json`.

    Attributes:
        schema_version: The version of this record's layout.
        category: The part the board is.
        image_id: The image's name within its run.
        image: The source image's path, as inference was given it.
        outcome: Accept, reject or needs review.
        reason: One sentence, written by code.
        review_cause: Why an engineer must decide; None unless the outcome is
            needs review.
        deciding_region: The index of the region the outcome rests on; None
            when it rests on no single region.
        clause: The clause applied to the deciding region, quoted whole.
        score: The anomaly model's raw image score.
        image_threshold: The raw score above which an image is anomalous.
        predicted_anomalous: Whether the anomaly model flagged the image.
        regions_found: Regions in the anomaly model's result.
        regions: The regions judged, in rank order.
        specification: The specification's title.
        judge_url: The VLM server asked.
        judge_model: The model's name on that server.
        created_at: When the decision was made, in UTC, ISO 8601.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = DECISION_SCHEMA_VERSION
    category: str
    image_id: str
    image: str
    outcome: Outcome
    reason: str = Field(min_length=1)
    review_cause: Cause | None = None
    deciding_region: int | None = None
    clause: schema.Clause | None = None
    score: float
    image_threshold: float
    predicted_anomalous: bool
    regions_found: int = Field(ge=0)
    regions: tuple[RegionDecision, ...] = ()
    specification: str
    judge_url: str
    judge_model: str
    created_at: str

    @property
    def regions_not_judged(self) -> int:
        """Regions the anomaly model found that were not put to the judge."""
        return self.regions_found - len(self.regions)


class Verdict(NamedTuple):
    """A board's outcome, combined from its regions.

    Attributes:
        outcome: Accept, reject or needs review.
        reason: One sentence.
        review_cause: Why an engineer must decide, when one must.
        deciding_region: The index of the region the outcome rests on, if one.
    """

    outcome: Outcome
    reason: str
    review_cause: Cause | None
    deciding_region: int | None


def refer_region(
    *,
    index: int,
    cause: Cause,
    reason: str,
    measurement: MeasuredRegion | None = None,
    from_peak: bool = False,
    answer: JudgeAnswer | None = None,
    clause: schema.Clause | None = None,
) -> RegionDecision:
    """Refer a region to an engineer for a cause the disposition rule does not know.

    Args:
        index: The region's index.
        cause: Why an engineer must decide.
        reason: The cause in words, without the closing phrase.
        measurement: The region as measured, if it was.
        from_peak: Whether the region is the peak-patch fallback.
        answer: The model's answer, if a valid one came.
        clause: The row of the clause table concerned, if one is.

    Returns:
        A needs-review decision with no figure compared.
    """
    return RegionDecision(
        index=index,
        outcome=Outcome.NEEDS_REVIEW,
        reason=reason + _ENGINEER,
        review_cause=cause,
        from_peak=from_peak,
        measurement=measurement,
        answer=answer,
        clause=clause,
    )


def _cited_row(
    specification: Specification, category: str, cited: str, zone: str | None
) -> schema.Clause | None:
    """Find the row of the part's own table that a citation points at.

    A numbered heading stands for its rows, and the row is the one for the
    zone the region was measured in; with no row for that zone the heading's
    first row is given, so the rule can say that the zone does not match. A
    row's own number is taken as that row.

    Args:
        specification: The parsed specification.
        category: The part the board is.
        cited: The heading or row number the model cited.
        zone: The zone the region was measured in, or None for no zone.

    Returns:
        The row, or None if the part's table has no such heading or row.
    """
    rows = [c for c in specification.clauses if c.category == category and c.heading_id == cited]
    if rows:
        return next((c for c in rows if c.zone in (zone, ANY_ZONE)), rows[0])
    return next(
        (c for c in specification.clauses if c.category == category and c.id == cited), None
    )


def decide_region(
    specification: Specification,
    category: str,
    *,
    index: int,
    measurement: MeasuredRegion,
    answer: JudgeAnswer,
    from_peak: bool = False,
) -> RegionDecision:
    """Decide what becomes of a measured region under the model's answer.

    Args:
        specification: The parsed specification.
        category: The part the board is; only its own clauses can be cited.
        index: The region's index.
        measurement: The region as measured.
        answer: The model's validated answer.
        from_peak: Whether the region is the peak-patch fallback.

    Returns:
        The region's decision. The outcome is the disposition rule's, except
        that an answer citing nothing, a region outside every zone of a part
        that has zones (the specification's scope refers those), a size limit
        on a region with no measured size, and a clause that itself refers
        for review are referred to an engineer.
    """
    if answer.defect_class is None or answer.clause_id is None:
        return refer_region(
            index=index,
            cause=Cause.NO_CLAUSE_APPLIES,
            reason=f"the judge found no clause of part {category} that covers the flagged area",
            measurement=measurement,
            from_peak=from_peak,
            answer=answer,
        )

    if measurement.zone is None and specification.zones_of(category):
        return refer_region(
            index=index,
            cause=Cause.OUTSIDE_ZONES,
            reason=(
                f"the flagged area lies outside every zone of part {category}, where the "
                "specification refers a defect for review"
            ),
            measurement=measurement,
            from_peak=from_peak,
            answer=answer,
        )

    row = _cited_row(specification, category, answer.clause_id, measurement.zone)
    rule = dispose(
        None if row is None else rule_clause(row),
        measurement,
        answer.defect_class,
        cited_clause_id=answer.clause_id,
    )
    if rule.outcome is not Outcome.NEEDS_REVIEW and row is not None:
        if from_peak and rule.measured is not None:
            return refer_region(
                index=index,
                cause=Cause.NOT_MEASURED,
                reason=(
                    f"clause {row.id} sets a size limit, but the flagged area is only the patch "
                    "under the anomaly map's peak and has no measured size"
                ),
                measurement=measurement,
                from_peak=from_peak,
                answer=answer,
                clause=row,
            )
        if row.disposition is schema.Disposition.REVIEW and rule.outcome is Outcome.REJECT:
            return RegionDecision(
                index=index,
                outcome=Outcome.NEEDS_REVIEW,
                reason=(
                    f"{rule.reason}; clause {row.id} refers this for review, "
                    "so an engineer must decide"
                ),
                review_cause=Cause.CLAUSE_ORDERS_REVIEW,
                from_peak=from_peak,
                measurement=measurement,
                answer=answer,
                clause=row,
                rule=rule,
            )
    return RegionDecision(
        index=index,
        outcome=rule.outcome,
        reason=rule.reason,
        review_cause=None if rule.review_cause is None else Cause(rule.review_cause.value),
        from_peak=from_peak,
        measurement=measurement,
        answer=answer,
        clause=row,
        rule=rule,
    )


def combine_regions(regions: Sequence[RegionDecision], *, found: int) -> Verdict:
    """Combine the decisions on a board's regions into the board's outcome.

    One rejected region rejects the board. Without a reject, one referred
    region refers the board, and so does any region that was not judged: a
    board is accepted only when every flagged area has been judged and
    accepted.

    Args:
        regions: The regions judged, in rank order.
        found: How many regions the anomaly model found.

    Returns:
        The outcome, its reason and the region it rests on.

    Raises:
        ValueError: If no region was judged.
    """
    if not regions:
        msg = "no region was judged, so there is nothing to combine"
        raise ValueError(msg)
    for outcome in (Outcome.REJECT, Outcome.NEEDS_REVIEW):
        first = next((region for region in regions if region.outcome is outcome), None)
        if first is not None:
            return Verdict(
                outcome, f"region {first.index}: {first.reason}", first.review_cause, first.index
            )
    left = found - len(regions)
    if left > 0:
        judged = (
            "the 1 flagged area judged is within its clause"
            if len(regions) == 1
            else f"the {len(regions)} flagged areas judged are within their clauses"
        )
        return Verdict(
            Outcome.NEEDS_REVIEW,
            f"{judged}, but {left} more were not judged{_ENGINEER}",
            Cause.NOT_JUDGED,
            None,
        )
    first = regions[0]
    return Verdict(
        Outcome.ACCEPT,
        f"every flagged area is within its clause; region {first.index}: {first.reason}",
        None,
        first.index,
    )
