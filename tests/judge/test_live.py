"""The marked live test: the real judge on five real crops of the pcb4 test run.

It needs what the default gate does not have: the anomaly model's pcb4 test
run under the settings' runs directory (`spec-to-inspector train --category
pcb4`) and the VLM server up (`scripts/serve_vlm.sh start`). It asserts the
judge's contract on whatever the model answers, and records the answers in
`results/stage1/judge.json`; whether the model named the right class is the
bench's figure to measure, not this test's to assert.

    uv run pytest -m live
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from spec_to_inspector.anomaly.ground_truth import defect_types
from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.judge.answer import answer_schema
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import RESULT_NAME, judge_run, load_decision
from spec_to_inspector.judge.timing import LiveAnswer, LiveRecord, update_results
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

ROOT = Path(__file__).parents[2]
CATEGORY = "pcb4"
LIVE_IMAGES = ("bad-000", "bad-002", "bad-016", "good-0320", "good-0871")
"""Three anomalous boards and two good boards the anomaly model flagged, so each has a crop."""
CONTEXT_TOKENS = 16384


@pytest.fixture(scope="module")
def specification() -> Specification:
    """The tracked clause table.

    Returns:
        The demo specification.
    """
    return read_clause_table(ROOT / "specs" / "pcb-spec.clauses.json")


@pytest.fixture(scope="module")
def decisions(specification: Specification) -> list[Decision]:
    """Judge the five images once, with the real server.

    Returns:
        The five decisions, in the order of `LIVE_IMAGES`.
    """
    settings = Settings()
    run = settings.runs_dir / CATEGORY / "test"
    with ChatClient(
        settings.vlm_url, settings.vlm_model, timeout_seconds=settings.vlm_timeout_seconds
    ) as client:
        made = judge_run(run, specification, client, image_ids=LIVE_IMAGES)

    answers: list[LiveAnswer] = []
    for decision in made:
        result = ImageResult.model_validate_json(
            (run / decision.image_id / RESULT_NAME).read_text(encoding="utf-8")
        )
        first = decision.regions[0]
        answers.append(
            LiveAnswer(
                image_id=decision.image_id,
                label=result.label,
                ground_truth=defect_types(CATEGORY, result.regions[0].ground_truth_values or []),
                regions_found=decision.regions_found,
                regions_judged=len(decision.regions),
                outcome=decision.outcome,
                reason=decision.reason,
                review_cause=decision.review_cause,
                clause_id=None if decision.clause is None else decision.clause.id,
                judge_reason=None if first.answer is None else first.answer.reason,
                judge_defect_class=None if first.answer is None else first.answer.defect_class,
                judge_clause_id=None if first.answer is None else first.answer.clause_id,
                seconds=None if first.call is None else first.call.seconds,
            )
        )
    update_results(
        ROOT / "results" / "stage1" / "judge.json",
        live=LiveRecord(
            measured_at=datetime.now(UTC).isoformat(timespec="seconds"),
            command=["pytest", *sys.argv[1:]],
            category=CATEGORY,
            run=str(run),
            judge_url=settings.vlm_url,
            judge_model=settings.vlm_model,
            answers=answers,
        ),
    )
    return made


@pytest.mark.live
def test_the_five_images_are_three_anomalous_boards_and_two_good_ones(
    decisions: list[Decision],
) -> None:
    """Every image was flagged, so every one has a crop the judge was shown."""
    assert [d.image_id for d in decisions] == list(LIVE_IMAGES)
    assert all(d.predicted_anomalous and d.regions for d in decisions)
    assert all(region.crop and region.overlay for d in decisions for region in d.regions)


@pytest.mark.live
def test_the_judge_was_reached_and_answered_within_the_schema(
    decisions: list[Decision], specification: Specification
) -> None:
    """Each region judged has a valid answer: a class and a heading of pcb4, or neither."""
    schema = answer_schema(specification, CATEGORY)
    properties = schema["properties"]
    assert isinstance(properties, dict)
    classes = properties["defect_class"]["enum"]
    headings = properties["clause_id"]["enum"]
    for decision in decisions:
        assert decision.review_cause is not Cause.SERVER_UNAVAILABLE, decision.reason
        for region in decision.regions:
            assert region.answer is not None, region.reason
            assert region.answer.defect_class in classes
            assert region.answer.clause_id in headings
            assert not any(character.isnumeric() for character in region.answer.reason)
            assert "\n" not in region.answer.reason
            assert region.call is not None
            assert region.call.attempts in (1, 2)
            assert region.call.prompt_tokens is not None
            assert region.call.prompt_tokens < CONTEXT_TOKENS


@pytest.mark.live
def test_every_decision_keeps_the_contract(decisions: list[Decision]) -> None:
    """Outcome, cause, clause and figures hang together, whatever the model said."""
    for decision in decisions:
        assert (decision.review_cause is not None) == (decision.outcome is Outcome.NEEDS_REVIEW)
        assert decision.reason
        for region in decision.regions:
            assert (region.review_cause is not None) == (region.outcome is Outcome.NEEDS_REVIEW)
            assert region.measurement is not None
            if region.rule is not None and region.rule.measured is not None:
                assert region.rule.measured == region.measurement.longest_extent_mm
                assert region.clause is not None
                assert region.rule.limit == region.clause.limit
            if region.outcome is not Outcome.NEEDS_REVIEW:
                assert region.clause is not None
                assert region.answer is not None
                assert region.clause.category == CATEGORY
                assert region.clause.heading_id == region.answer.clause_id
                assert region.clause.defect_class == region.answer.defect_class
                assert region.clause.zone in (region.measurement.zone, "any")
        if decision.outcome is Outcome.REJECT:
            assert decision.clause is not None
            assert decision.clause.disposition.value == "reject"


@pytest.mark.live
def test_each_decision_is_on_disk_beside_the_anomaly_models_result(
    decisions: list[Decision],
) -> None:
    """`decision.json` reads back as the decision made."""
    run = Settings().runs_dir / CATEGORY / "test"
    for decision in decisions:
        assert load_decision(run / decision.image_id) == decision
