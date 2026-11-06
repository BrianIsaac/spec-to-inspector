"""Tests for what the bench keeps of a judged image: here, the reasons with a digit in them."""

import json

import pytest

from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.bench.observe import digit_reasons_of, observe
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.decision import Decision, JudgeCall, RegionDecision
from spec_to_inspector.judge.disposition import Outcome
from tests.bench.bench_fakes import REPLIES, seen


def _listed(*texts: str, stood: str | None = None) -> list[tuple[str, bool, bool]]:
    """Run some model texts through `observe`, as one area's answers.

    Args:
        *texts: What the model wrote, in order.
        stood: The reason of the answer that stood; None if none did.

    Returns:
        Each reason listed, whether it stood, and whether a unit follows a digit in it.
    """
    region = RegionDecision.model_construct(
        index=1,
        outcome=Outcome.NEEDS_REVIEW,
        review_cause=None,
        call=JudgeCall.model_construct(texts=texts, attempts=len(texts), seconds=1.0),
        answer=None
        if stood is None
        else JudgeAnswer.model_validate(
            {"reason": stood, "defect_class": "melt", "clause_id": "4.1"},
            context={"reason_rule": "designators"},
        ),
        clause=None,
        corrections=(),
    )
    decision = Decision.model_construct(
        outcome=Outcome.NEEDS_REVIEW,
        review_cause=None,
        regions=(region,),
        corrected=type("Corrected", (), {"in_prompt": False})(),
    )
    result = ImageResult.model_construct(
        category="pcb4",
        image_id="bad-080",
        label="bad",
        score=40.0,
        regions=[type("Region", (), {"index": 1})()],
        ground_truth_mask=None,
    )
    seen_image = observe(decision, result, judge_seconds=1.0)
    return [(r.reason, r.valid, r.followed_by_a_unit) for r in seen_image.digit_reasons]


def _text(reason: str) -> str:
    return json.dumps({"reason": reason, "defect_class": "melt", "clause_id": "4.1"})


def test_a_reason_with_no_digit_is_not_listed() -> None:
    """The ordinary case: nothing to report, and every one of the fake's replies is that."""
    for reply in REPLIES:
        assert _listed(reply) == []


def test_a_designator_is_listed_and_is_no_size() -> None:
    """Listed as the protocol asks, with nothing after it that measures."""
    reason = "A resistor R12 is present and correctly placed but has foreign material on it."
    assert _listed(_text(reason), stood=reason) == [(reason, True, False)]


@pytest.mark.parametrize(
    "reason",
    [
        "R5 mm",
        "A5mm",
        "a mark across R5 millimetres",
        "U3 MM",
        "C12 micrometres of it",
        "R1 cm",
        "R3 inches",
        "R3 mils",
        "R3 µm",
    ],
)
def test_a_digit_followed_by_a_unit_of_length_is_counted(reason: str) -> None:
    """One of these is enough to say the pattern passes a size."""
    assert _listed(_text(reason), stood=reason) == [(reason, True, True)]


@pytest.mark.parametrize(
    "reason",
    ["R5 in the corner", "R5 mounted crooked", "C12 missing", "U3 marked", "R5, mm scale"],
)
def test_a_word_that_only_starts_like_a_unit_is_not_counted(reason: str) -> None:
    """A designator followed by ordinary words is what the comparison is there to let through."""
    assert _listed(_text(reason), stood=reason) == [(reason, True, False)]


def test_a_refused_answer_is_listed_too_and_says_it_did_not_stand() -> None:
    """Week 1's fifth retry was `½`: the model wrote it, so the listing shows it."""
    assert _listed(
        _text("about ½ of the pad"), _text("a mark on the pad"), stood="a mark on the pad"
    ) == [("about ½ of the pad", False, False)]


def test_an_answer_cut_off_at_the_token_limit_is_still_read() -> None:
    """A padded answer is not JSON; its reason is read up to where it stops."""
    cut_off = '{"reason": "a mark on R12 and R13 padded with nothing'
    assert _listed(cut_off) == [("a mark on R12 and R13 padded with nothing", False, False)]
    assert _listed("not an answer at all, R12") == []
    assert _listed('["a list", "R12"]') == []
    assert _listed('{"reason": 12}') == []


def test_a_runs_reasons_are_gathered_with_how_many_a_unit_follows() -> None:
    """Board by board, in the run's order."""
    plain = seen("pcb4", "bad-001", "scratch")
    assert digit_reasons_of([plain]).reasons == ()
    assert digit_reasons_of([plain]).followed_by_a_unit == 0
