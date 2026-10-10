"""Tests for the disposition rule: worked examples, then properties over any input."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from spec_to_inspector.judge.disposition import (
    Clause,
    Comparison,
    Disposition,
    Outcome,
    Quantity,
    ReviewCause,
    dispose,
)
from spec_to_inspector.measure.models import MeasuredRegion

_BORDER_NOTE = "touches the image border"


def _region(
    longest_mm: float = 0.72,
    *,
    area_mm2: float = 0.2,
    zone: str | None = "A",
    touches_border: bool = False,
) -> MeasuredRegion:
    return MeasuredRegion(
        label=1,
        area_px=12,
        area_mm2=area_mm2,
        longest_extent_mm=longest_mm,
        shortest_extent_mm=0.0,
        centroid=(0.5, 0.5),
        bbox_px=(0, 0, 4, 3),
        rectangle_px=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)),
        touches_border=touches_border,
        zone=zone,
    )


def _clause(
    comparison: Comparison | str = ">",
    limit: float | None = 0.5,
    *,
    clause_id: str = "4.2.1",
    defect_class: str = "scratch",
    zone: str | None = "A",
    unit: str | None = "mm",
    disposition: Outcome | str = "reject",
) -> Clause:
    return Clause.model_validate(
        {
            "id": clause_id,
            "defect_class": defect_class,
            "zone": zone,
            "limit": limit,
            "unit": unit,
            "comparison": comparison,
            "disposition": disposition,
        }
    )


def test_a_scratch_over_its_limit_is_rejected_in_words_a_manager_reads() -> None:
    """The reject names the measurement, the limit, the clause and the zone."""
    decision = dispose(_clause(), _region(0.72), "scratch")

    assert decision.outcome is Outcome.REJECT
    assert decision.reason == (
        "longest extent 0.72 mm exceeds the 0.5 mm limit of clause 4.2.1 in zone A"
    )
    assert decision.review_cause is None


def test_a_scratch_under_its_limit_is_accepted() -> None:
    """What does not meet a reject clause's condition is accepted under that clause."""
    decision = dispose(_clause(), _region(0.31), "scratch")

    assert decision.outcome is Outcome.ACCEPT
    assert decision.reason == (
        "longest extent 0.31 mm does not exceed the 0.5 mm limit of clause 4.2.1 in zone A"
    )


def test_the_decision_carries_its_numbers_as_given() -> None:
    """The reject card reads the measurement and the limit from fields, not from the sentence."""
    decision = dispose(_clause(), _region(0.72), "scratch")

    assert decision == Disposition(
        outcome=Outcome.REJECT,
        reason=decision.reason,
        review_cause=None,
        clause_id="4.2.1",
        defect_class="scratch",
        zone="A",
        quantity=Quantity.LONGEST_EXTENT,
        measured=0.72,
        limit=0.5,
        unit="mm",
        comparison=Comparison.GREATER,
    )


@pytest.mark.parametrize(
    ("comparison", "measured", "outcome", "words"),
    [
        (">", 0.5, Outcome.ACCEPT, "does not exceed"),
        (">", 0.51, Outcome.REJECT, "exceeds"),
        (">=", 0.5, Outcome.REJECT, "is at or above"),
        (">=", 0.49, Outcome.ACCEPT, "is below"),
        ("<", 0.5, Outcome.ACCEPT, "is at or above"),
        ("<", 0.49, Outcome.REJECT, "is below"),
        ("<=", 0.5, Outcome.REJECT, "does not exceed"),
        ("<=", 0.51, Outcome.ACCEPT, "exceeds"),
    ],
)
def test_each_comparison_at_and_beside_its_limit(
    comparison: str, measured: float, outcome: Outcome, words: str
) -> None:
    """A reject clause rejects when its comparison holds, and the limit itself falls as written."""
    decision = dispose(_clause(comparison), _region(measured), "scratch")

    assert decision.outcome is outcome
    assert f" mm {words} the 0.5 mm limit" in decision.reason


def test_a_clause_that_accepts_under_a_limit_rejects_over_it() -> None:
    """An accept clause is the same rule read the other way."""
    clause = _clause("<=", disposition="accept")

    assert dispose(clause, _region(0.5), "scratch").outcome is Outcome.ACCEPT
    assert dispose(clause, _region(0.72), "scratch").outcome is Outcome.REJECT


def test_an_unconditional_clause_rejects_whatever_the_size() -> None:
    """A missing component is rejected in any zone; no size enters the reason."""
    clause = _clause(
        "unconditional", None, clause_id="4.3.1", defect_class="missing", zone=None, unit=None
    )

    decision = dispose(clause, _region(0.01, zone="B"), "missing")

    assert decision.outcome is Outcome.REJECT
    assert decision.reason == "clause 4.3.1 rejects 'missing' in any zone, whatever its size"
    assert (decision.measured, decision.limit, decision.quantity) == (None, None, None)


def test_an_unconditional_clause_ignores_a_stray_limit() -> None:
    """A limit left on an unconditional clause changes nothing."""
    clause = _clause("unconditional", 0.5, defect_class="burnt")

    decision = dispose(clause, _region(0.01), "burnt")

    assert decision.outcome is Outcome.REJECT
    assert decision.reason == "clause 4.2.1 rejects 'burnt' in zone A, whatever its size"


def test_an_area_limit_is_compared_with_the_area() -> None:
    """A limit in square millimetres is about the region's area, not its length."""
    clause = _clause(">", 1.0, defect_class="dirt", unit="mm2", zone=None)

    decision = dispose(clause, _region(0.2, area_mm2=1.25, zone="B"), "dirt")

    assert decision.outcome is Outcome.REJECT
    assert decision.reason == "area 1.25 mm² exceeds the 1 mm² limit of clause 4.2.1"
    assert (decision.quantity, decision.measured, decision.unit) == (Quantity.AREA, 1.25, "mm2")


@pytest.mark.parametrize("unit", ["mm2", "mm^2", "mm²", " MM2 "])
def test_square_millimetres_may_be_spelled_several_ways(unit: str) -> None:
    """The parser's spelling of the unit does not decide the measurement."""
    clause = _clause(">", 1.0, unit=unit)

    assert dispose(clause, _region(area_mm2=1.25), "scratch").quantity is Quantity.AREA


def test_a_missing_clause_needs_review() -> None:
    """A clause id the specification does not hold is never guessed at."""
    decision = dispose(None, _region(), "scratch", cited_clause_id="9.9.9")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is ReviewCause.MISSING_CLAUSE
    assert decision.reason == (
        "clause 9.9.9 is not in the specification, so no limit applies; an engineer must decide"
    )
    assert decision.clause_id == "9.9.9"


def test_no_clause_cited_at_all_needs_review() -> None:
    """Without even an id there is still a reason."""
    decision = dispose(None, _region(), "scratch")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.reason == "no clause was cited, so no limit applies; an engineer must decide"
    assert decision.clause_id is None


def test_a_class_that_does_not_match_the_clause_needs_review() -> None:
    """A scratch judged under the dirt clause is a mistake for a person to settle."""
    decision = dispose(_clause(defect_class="dirt"), _region(0.72), "scratch")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is ReviewCause.CLASS_MISMATCH
    assert decision.reason == (
        "the defect was named 'scratch', but clause 4.2.1 covers 'dirt'; an engineer must decide"
    )


def test_class_names_match_whatever_their_case_and_spacing() -> None:
    """VisA writes "wrong place" with a space; a capital or a doubled space is the same class."""
    clause = _clause("unconditional", None, defect_class="Wrong  Place")

    assert dispose(clause, _region(), " wrong place ").outcome is Outcome.REJECT
    assert clause.defect_class == "wrong place"


def test_a_clause_for_another_zone_needs_review() -> None:
    """The lenient zone's limit cannot settle a region that reaches the strict zone."""
    decision = dispose(_clause(zone="B", limit=1.0), _region(0.72, zone="A"), "scratch")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is ReviewCause.ZONE_MISMATCH
    assert decision.reason == (
        "clause 4.2.1 applies in zone B, but the region lies in zone A; an engineer must decide"
    )


def test_a_zoned_clause_cannot_settle_a_region_outside_every_zone() -> None:
    """Where the specification drew no zone, a zone's limit does not apply by itself."""
    decision = dispose(_clause(), _region(0.72, zone=None), "scratch")

    assert decision.review_cause is ReviewCause.ZONE_MISMATCH
    assert decision.reason == (
        "clause 4.2.1 applies in zone A, but the region lies outside every zone; "
        "an engineer must decide"
    )


def test_a_clause_for_any_zone_applies_everywhere() -> None:
    """No zone on the clause means every zone, and no zone at all."""
    clause = _clause(zone=None)

    assert dispose(clause, _region(0.72, zone="B"), "scratch").outcome is Outcome.REJECT
    assert dispose(clause, _region(0.72, zone=None), "scratch").outcome is Outcome.REJECT


def test_a_comparison_without_a_limit_needs_review() -> None:
    """A clause the parser left half-read is not completed by a guess."""
    decision = dispose(_clause(">", None), _region(), "scratch")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is ReviewCause.UNDEFINED_MEASUREMENT
    assert decision.reason == (
        "clause 4.2.1 compares a size with a limit but states no limit; an engineer must decide"
    )


@pytest.mark.parametrize(
    ("unit", "words"),
    [
        ("deg", "states its limit in 'deg', which the inspector does not measure"),
        ("%", "states its limit in '%', which the inspector does not measure"),
        (None, "states no unit for its limit"),
    ],
)
def test_a_measurement_the_inspector_does_not_make_needs_review(
    unit: str | None, words: str
) -> None:
    """An angle, a percentage or a bare number is not a length or an area."""
    decision = dispose(_clause(unit=unit), _region(), "scratch")

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is ReviewCause.UNDEFINED_MEASUREMENT
    assert decision.reason == f"clause 4.2.1 {words}; an engineer must decide"


def test_the_words_never_contradict_the_decision() -> None:
    """0.5004 mm is over a 0.5 mm limit; to two places it would read 0.50 and seem not to be."""
    decision = dispose(_clause(), _region(0.5004), "scratch")

    assert decision.outcome is Outcome.REJECT
    assert decision.reason.startswith("longest extent 0.5004 mm exceeds the 0.5 mm limit")


def test_a_region_at_the_border_says_so() -> None:
    """Its measured size may be less than its true size, and the reader is told."""
    decision = dispose(_clause(), _region(0.31, touches_border=True), "scratch")

    assert decision.outcome is Outcome.ACCEPT
    assert decision.reason.endswith(
        "in zone A (the region touches the image border, so its true size may be larger)"
    )


def test_a_clause_can_only_accept_or_reject() -> None:
    """Needs review is the rule's own answer, never something a clause orders."""
    with pytest.raises(ValidationError):
        _clause(disposition="needs review")


@pytest.mark.parametrize("limit", [-0.1, float("nan"), float("inf")])
def test_a_limit_is_a_size(limit: float) -> None:
    """A negative, missing-number or endless limit is not a limit."""
    with pytest.raises(ValidationError):
        _clause(limit=limit)


def test_an_unknown_comparison_is_refused() -> None:
    """The five comparisons are the whole grammar."""
    with pytest.raises(ValidationError):
        _clause("!=")


def test_a_clause_and_a_decision_survive_json() -> None:
    """Both are plain data: what is written to a sidecar reads back equal."""
    clause = _clause()
    decision = dispose(clause, _region(), "scratch")

    assert Clause.model_validate_json(clause.model_dump_json()) == clause
    assert Disposition.model_validate_json(decision.model_dump_json()) == decision
    assert '"outcome":"reject"' in decision.model_dump_json()


_CLASSES = ["melt", "scratch", "missing", "bent", "dirt", "extra", "wrong place", "damage", "burnt"]
_ZONES = st.sampled_from([None, "A", "B", "C"])
_SIZES = st.floats(min_value=0.0, max_value=1e4, allow_nan=False)
_LIMITS = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1e4, allow_nan=False))
_UNITS = st.sampled_from(["mm", "mm2", "mm^2", "mm²", "deg", "%", "cm", "m3", None])
_IDS = st.from_regex(r"[1-9]\.[1-9]\.[1-9]{1,2}", fullmatch=True)
_CONDITIONAL = [">", ">=", "<", "<="]

_regions = st.builds(
    _region,
    _SIZES,
    area_mm2=_SIZES,
    zone=_ZONES,
    touches_border=st.booleans(),
)
_clauses = st.builds(
    _clause,
    st.sampled_from([*_CONDITIONAL, "unconditional"]),
    _LIMITS,
    clause_id=_IDS,
    defect_class=st.sampled_from(_CLASSES),
    zone=_ZONES,
    unit=_UNITS,
    disposition=st.sampled_from(["accept", "reject"]),
)


@given(
    st.one_of(st.none(), _clauses), _regions, st.sampled_from(_CLASSES), st.one_of(st.none(), _IDS)
)
def test_every_path_returns_a_decision_with_a_reason(
    clause: Clause | None, region: MeasuredRegion, defect_class: str, cited: str | None
) -> None:
    """Whatever comes in, an outcome and a sentence come out, and review always says why."""
    decision = dispose(clause, region, defect_class, cited_clause_id=cited)

    assert decision.outcome in set(Outcome)
    assert decision.reason.strip()
    assert (decision.outcome is Outcome.NEEDS_REVIEW) == (decision.review_cause is not None)
    if decision.outcome is Outcome.NEEDS_REVIEW:
        assert decision.reason.endswith("; an engineer must decide")


@given(
    st.sampled_from(_CONDITIONAL),
    st.floats(min_value=0.0, max_value=1e4, allow_nan=False),
    st.sampled_from(["mm", "mm2"]),
    st.sampled_from(["accept", "reject"]),
    _SIZES,
    _SIZES,
)
def test_the_rule_is_monotone_in_the_measurement(
    comparison: str, limit: float, unit: str, disposition: str, first: float, second: float
) -> None:
    """A larger defect never fares better under a "greater than" clause, nor worse under "less"."""
    clause = _clause(comparison, limit, unit=unit, disposition=disposition)
    smaller, larger = sorted((first, second))

    held = [
        dispose(clause, _region(size, area_mm2=size), "scratch").outcome is clause.disposition
        for size in (smaller, larger)
    ]

    if comparison in {">", ">="}:
        assert held[0] <= held[1]
    else:
        assert held[0] >= held[1]


@given(
    st.one_of(st.none(), _clauses), _regions, st.sampled_from(_CLASSES), st.one_of(st.none(), _IDS)
)
def test_no_number_comes_from_outside_the_inputs(
    clause: Clause | None, region: MeasuredRegion, defect_class: str, cited: str | None
) -> None:
    """Every figure in the reason is the clause's limit or the region's measurement, rounded."""
    decision = dispose(clause, region, defect_class, cited_clause_id=cited)

    words = decision.reason
    for clause_id in (clause.id if clause else None, cited):
        if clause_id is not None:
            words = words.replace(f"clause {clause_id}", "clause")
    if clause is not None and clause.unit is not None:
        words = words.replace(f"'{clause.unit}'", "")
    measurements = (region.longest_extent_mm, region.area_mm2)
    allowed = {float(f"{value:.{places}f}") for value in measurements for places in range(2, 18)}
    allowed.update(measurements)
    if clause is not None and clause.limit is not None:
        allowed.add(clause.limit)
    for figure in re.findall(r"\d+(?:\.\d+)?", words):
        assert float(figure) in allowed, (figure, decision.reason)

    assert decision.measured in {None, *measurements}
    assert decision.limit in {None, clause.limit if clause else None}


@given(
    st.sampled_from(_CONDITIONAL),
    st.floats(min_value=0.0, max_value=1e4, allow_nan=False),
    _SIZES,
    st.sampled_from(["accept", "reject"]),
)
def test_the_printed_figures_compare_the_way_the_decision_went(
    comparison: str, limit: float, size: float, disposition: str
) -> None:
    """Read back from the sentence, the measurement stands to the limit as the exact one does."""
    clause = _clause(comparison, limit, disposition=disposition)

    decision = dispose(clause, _region(size), "scratch")

    printed, printed_limit = (
        float(figure) for figure in re.findall(r"(\d+(?:\.\d+)?) mm", decision.reason)
    )
    compare = {
        ">": printed > printed_limit,
        ">=": printed >= printed_limit,
        "<": printed < printed_limit,
        "<=": printed <= printed_limit,
    }
    assert printed_limit == limit
    assert compare[comparison] == (decision.outcome is clause.disposition)


def _two_regions_in(zone: str | None) -> st.SearchStrategy[tuple[MeasuredRegion, MeasuredRegion]]:
    one = st.builds(_region, _SIZES, area_mm2=_SIZES, zone=st.just(zone))
    return st.tuples(one, one)


@given(
    st.builds(
        _clause,
        st.just("unconditional"),
        _LIMITS,
        defect_class=st.sampled_from(_CLASSES),
        zone=_ZONES,
        unit=_UNITS,
        disposition=st.sampled_from(["accept", "reject"]),
    ),
    _ZONES.flatmap(_two_regions_in),
)
def test_an_unconditional_clause_does_not_look_at_the_size(
    clause: Clause, regions: tuple[MeasuredRegion, MeasuredRegion]
) -> None:
    """Two regions in the same zone get the same answer from a clause without a comparison."""
    first, second = (dispose(clause, region, clause.defect_class) for region in regions)

    assert first == second


def test_the_border_note_is_only_for_measured_sizes() -> None:
    """An unconditional reject does not hang on a size, so the border does not qualify it."""
    clause = _clause("unconditional", None)

    decision = dispose(clause, _region(touches_border=True), "scratch")

    assert _BORDER_NOTE not in decision.reason
