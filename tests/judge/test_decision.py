"""Tests for the composition of the judge's answer and the disposition rule."""

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.decision import (
    Cause,
    RegionDecision,
    combine_regions,
    decide_region,
    refer_region,
)
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.measure import MeasuredRegion
from spec_to_inspector.spec.schema import Disposition, Specification, read_clause_table
from tests.spec.spec_fakes import sized_clause, specification, unconditional_clause

PCB_SPEC = Path(__file__).parents[2] / "specs" / "pcb-spec.clauses.json"


def _region(extent: float = 0.75, zone: str | None = "A") -> MeasuredRegion:
    return MeasuredRegion(
        label=1,
        area_px=180,
        area_mm2=0.45,
        longest_extent_mm=extent,
        shortest_extent_mm=0.3,
        centroid=(0.5, 0.5),
        bbox_px=(300, 400, 330, 406),
        rectangle_px=((300.0, 400.0), (330.0, 400.0), (330.0, 406.0), (300.0, 406.0)),
        touches_border=False,
        zone=zone,
    )


def _answer(defect_class: str | None = "scratch", clause_id: str | None = "4.1") -> JudgeAnswer:
    return JudgeAnswer(
        reason="a thin bright line scored across the board face",
        defect_class=defect_class,
        clause_id=clause_id,
    )


def _decide(
    answer: JudgeAnswer,
    region: MeasuredRegion | None = None,
    *,
    spec: Specification | None = None,
    category: str = "pcb9",
    from_peak: bool = False,
) -> RegionDecision:
    return decide_region(
        spec if spec is not None else specification(),
        category,
        index=1,
        measurement=region if region is not None else _region(),
        answer=answer,
        from_peak=from_peak,
    )


def test_a_valid_answer_over_the_limit_is_a_reject_with_the_clause_quoted() -> None:
    """The heading is the model's; the zone's row, the limit and the size are the code's."""
    decision = _decide(_answer(), _region(extent=0.75, zone="A"))

    assert decision.outcome is Outcome.REJECT
    assert decision.review_cause is None
    assert (
        decision.reason
        == "longest extent 0.75 mm exceeds the 0.5 mm limit of clause 4.1.1 in zone A"
    )
    assert decision.clause is not None
    assert decision.clause.id == "4.1.1"
    assert decision.clause.source_text == "A scratch longer than the limit of its zone is rejected."
    assert decision.clause.page == 3
    assert decision.rule is not None
    assert decision.rule.measured == 0.75
    assert decision.rule.limit == 0.5
    assert decision.answer == _answer()


def test_the_zones_row_is_chosen_by_the_measured_zone() -> None:
    """The same heading in zone B is the lenient row, and the same scratch is accepted."""
    decision = _decide(_answer(), _region(extent=0.75, zone="B"))

    assert decision.outcome is Outcome.ACCEPT
    assert decision.clause is not None
    assert decision.clause.id == "4.1.2"
    assert decision.reason == (
        "longest extent 0.75 mm does not exceed the 1 mm limit of clause 4.1.2 in zone B"
    )


def test_an_unconditional_clause_rejects_whatever_the_size() -> None:
    """A missing component rejects in any zone."""
    decision = _decide(_answer("missing", "4.2"), _region(zone=None))

    assert decision.outcome is Outcome.REJECT
    assert decision.reason == "clause 4.2 rejects 'missing' in any zone, whatever its size"
    assert decision.rule is not None
    assert decision.rule.measured is None


def test_an_unknown_clause_is_needs_review() -> None:
    """A clause the specification does not have is never guessed at."""
    decision = _decide(_answer("scratch", "9.9"))

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.MISSING_CLAUSE
    assert decision.reason == (
        "clause 9.9 is not in the specification, so no limit applies; an engineer must decide"
    )
    assert decision.clause is None


def test_a_clause_of_another_part_is_an_unknown_clause() -> None:
    """A pcb1 heading cited for a pcb4 board is not in that board's table."""
    spec = read_clause_table(PCB_SPEC)

    decision = _decide(_answer("scratch", "4.2"), spec=spec, category="pcb4")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.MISSING_CLAUSE
    assert decision.clause is None


def test_a_class_that_is_not_its_clauses_class_is_needs_review() -> None:
    """The class named and the clause cited must agree."""
    decision = _decide(_answer("missing", "4.1"))

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.CLASS_MISMATCH
    assert decision.reason == (
        "the defect was named 'missing', but clause 4.1.1 covers 'scratch'; an engineer must decide"
    )
    assert decision.rule is not None
    assert decision.rule.measured is None


def test_an_answer_that_cites_nothing_is_needs_review() -> None:
    """The model's way out is a referral, never an accept."""
    decision = _decide(_answer(None, None))

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.NO_CLAUSE_APPLIES
    assert decision.reason == (
        "the judge found no clause of part pcb9 that covers the flagged area; "
        "an engineer must decide"
    )
    assert decision.clause is None
    assert decision.rule is None


def test_a_sized_clause_outside_every_zone_is_needs_review() -> None:
    """A limit belongs to a zone; a region in none has no limit to meet."""
    spec = specification(
        zones=(specification().zones[0],),
        clauses=(sized_clause("4.1.1", "A"), unconditional_clause("4.2")),
    )

    decision = _decide(_answer(), _region(zone=None), spec=spec)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.ZONE_MISMATCH
    assert "outside every zone" in decision.reason


def test_a_row_cited_by_its_own_number_is_held_to_its_zone() -> None:
    """A server that does not constrain may cite a row; the wrong zone's row is a referral."""
    right = _decide(_answer("scratch", "4.1.1"), _region(zone="A"))
    wrong = _decide(_answer("scratch", "4.1.2"), _region(zone="A"))

    assert right.outcome is Outcome.REJECT
    assert wrong.outcome is Outcome.NEEDS_REVIEW
    assert wrong.review_cause is Cause.ZONE_MISMATCH


def test_a_peak_patch_is_not_measured_against_a_size_limit() -> None:
    """The patch's size is the patch's, so a sized clause on it is a referral with no figure."""
    decision = _decide(_answer(), _region(extent=5.0), from_peak=True)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.NOT_MEASURED
    assert decision.reason == (
        "clause 4.1.1 sets a size limit, but the flagged area is only the patch under the "
        "anomaly map's peak and has no measured size; an engineer must decide"
    )
    assert decision.rule is None
    assert decision.from_peak


def test_a_peak_patch_under_an_unconditional_clause_is_still_decided() -> None:
    """A missing component needs no size."""
    decision = _decide(_answer("missing", "4.2"), from_peak=True)

    assert decision.outcome is Outcome.REJECT


def test_a_clause_that_refers_for_review_is_needs_review_when_its_limit_is_met() -> None:
    """The specification's own referral is kept, with the measurement that triggered it."""
    spec = specification(
        clauses=(
            sized_clause("4.1.1", "A", disposition=Disposition.REVIEW),
            sized_clause("4.1.2", "B", limit=1.0, limit_text="1.0 mm max"),
            unconditional_clause("4.2"),
        )
    )

    over = _decide(_answer(), _region(extent=0.75), spec=spec)
    under = _decide(_answer(), _region(extent=0.25), spec=spec)

    assert over.outcome is Outcome.NEEDS_REVIEW
    assert over.review_cause is Cause.CLAUSE_ORDERS_REVIEW
    assert over.reason == (
        "longest extent 0.75 mm exceeds the 0.5 mm limit of clause 4.1.1 in zone A; "
        "clause 4.1.1 refers this for review, so an engineer must decide"
    )
    assert under.outcome is Outcome.ACCEPT


@given(
    extent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    zone=st.sampled_from(["A", "B", None]),
    defect_class=st.sampled_from(["scratch", "missing", "dirt", None]),
    clause_id=st.sampled_from(["4.1", "4.2", "4.1.1", "4.1.2", "9.9", "5.6"]),
    from_peak=st.booleans(),
)
def test_every_number_in_a_region_decision_is_the_measurements_or_the_clauses(
    extent: float, zone: str | None, defect_class: str | None, clause_id: str, from_peak: bool
) -> None:
    """Whatever the model answers, the figures are the region's and the clause's own."""
    region = _region(extent=extent, zone=zone)
    answer = _answer(defect_class, clause_id if defect_class is not None else None)

    decision = _decide(answer, region, from_peak=from_peak)

    assert decision.measurement == region
    assert decision.answer == answer
    assert (decision.review_cause is not None) == (decision.outcome is Outcome.NEEDS_REVIEW)
    assert decision.reason
    if decision.rule is not None and decision.rule.measured is not None:
        assert decision.rule.measured == region.longest_extent_mm
        assert decision.clause is not None
        assert decision.rule.limit == decision.clause.limit
    if decision.outcome is not Outcome.NEEDS_REVIEW:
        assert decision.clause is not None
        assert decision.clause.defect_class == answer.defect_class
        assert decision.clause.zone in (region.zone, "any")


def test_a_referral_made_outside_the_rule_carries_its_cause_and_no_figure() -> None:
    """A region the judge could not be asked about is referred with the cause in words."""
    decision = refer_region(
        index=2,
        cause=Cause.SERVER_UNAVAILABLE,
        reason="the judge could not be asked: cannot reach the VLM server",
        measurement=_region(),
    )

    assert decision.index == 2
    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.SERVER_UNAVAILABLE
    assert decision.reason.endswith("; an engineer must decide")
    assert decision.rule is None
    assert decision.clause is None
    assert decision.answer is None


def _decided(index: int, outcome: Outcome) -> RegionDecision:
    if outcome is Outcome.NEEDS_REVIEW:
        return _decide(_answer("scratch", "9.9")).model_copy(update={"index": index})
    extent = 0.75 if outcome is Outcome.REJECT else 0.25
    return _decide(_answer(), _region(extent=extent)).model_copy(update={"index": index})


def test_one_reject_rejects_the_board_and_names_its_region() -> None:
    """A board is rejected on its first rejecting region, whatever the others are."""
    regions = [_decided(1, Outcome.NEEDS_REVIEW), _decided(2, Outcome.REJECT)]

    verdict = combine_regions(regions, found=2)

    assert verdict.outcome is Outcome.REJECT
    assert verdict.deciding_region == 2
    assert verdict.review_cause is None
    assert verdict.reason == (
        "region 2: longest extent 0.75 mm exceeds the 0.5 mm limit of clause 4.1.1 in zone A"
    )


def test_without_a_reject_one_referral_refers_the_board() -> None:
    """An accept needs every region accepted."""
    regions = [_decided(1, Outcome.ACCEPT), _decided(2, Outcome.NEEDS_REVIEW)]

    verdict = combine_regions(regions, found=2)

    assert verdict.outcome is Outcome.NEEDS_REVIEW
    assert verdict.deciding_region == 2
    assert verdict.review_cause is Cause.MISSING_CLAUSE
    assert verdict.reason.startswith("region 2: clause 9.9 is not in the specification")


def test_every_region_accepted_accepts_the_board() -> None:
    """The board's accept quotes its most anomalous region."""
    regions = [_decided(1, Outcome.ACCEPT), _decided(2, Outcome.ACCEPT)]

    verdict = combine_regions(regions, found=2)

    assert verdict.outcome is Outcome.ACCEPT
    assert verdict.deciding_region == 1
    assert verdict.reason == (
        "every flagged area is within its clause; region 1: longest extent 0.25 mm does not "
        "exceed the 0.5 mm limit of clause 4.1.1 in zone A"
    )


def test_accepted_regions_with_others_not_judged_refer_the_board() -> None:
    """An area nobody looked at cannot be accepted."""
    verdict = combine_regions([_decided(1, Outcome.ACCEPT)], found=4)

    assert verdict.outcome is Outcome.NEEDS_REVIEW
    assert verdict.review_cause is Cause.NOT_JUDGED
    assert verdict.deciding_region is None
    assert verdict.reason == (
        "the 1 flagged area judged is within its clause, but 3 more were not judged; "
        "an engineer must decide"
    )


def test_a_reject_stands_even_with_regions_not_judged() -> None:
    """One nonconforming area is enough to reject."""
    verdict = combine_regions([_decided(1, Outcome.REJECT)], found=5)

    assert verdict.outcome is Outcome.REJECT
    assert verdict.deciding_region == 1


def test_no_regions_cannot_be_combined() -> None:
    """A board without a flagged area is not this function's to decide."""
    with pytest.raises(ValueError, match="no region"):
        combine_regions([], found=0)
