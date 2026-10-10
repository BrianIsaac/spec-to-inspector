"""The marked live test of the corrections loop: one scripted pair on the real judge.

It needs the anomaly model's pcb4 test run under the settings' runs directory
and the VLM server up (`scripts/serve_vlm.sh start`). It holds the judge to
the loop's contract on whatever the model answers: the override recorded for
the misjudged image is the line in its sibling's prompt, the decision says so,
and the answer after it is still a valid one that code decided. Whether the
correction fixed the sibling is recorded by the check, not asserted here:

    uv run pytest -m live
    uv run python -m spec_to_inspector.corrections.live_check
"""

from pathlib import Path

import pytest

from spec_to_inspector.corrections.live_check import DEFAULT_PAIRS, PairDecisions, check_pair
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.answer import answer_schema
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

ROOT = Path(__file__).parents[2]
PAIR = DEFAULT_PAIRS[0]


@pytest.fixture(scope="module")
def specification() -> Specification:
    """The tracked clause table.

    Returns:
        The demo specification.
    """
    return read_clause_table(ROOT / "specs" / "pcb-spec.clauses.json")


@pytest.fixture(scope="module")
def checked(
    specification: Specification, tmp_path_factory: pytest.TempPathFactory
) -> PairDecisions:
    """Judge the first scripted pair once, with the real server and a scratch store.

    Returns:
        The pair's record and the decisions behind it.
    """
    settings = Settings()
    store = CorrectionStore(tmp_path_factory.mktemp("live") / "pair.sqlite3")
    with ChatClient(
        settings.vlm_url, settings.vlm_model, timeout_seconds=settings.vlm_timeout_seconds
    ) as client:
        return check_pair(
            PAIR, settings.runs_dir / PAIR.category / "test", specification, client, store
        )


def _after(checked: PairDecisions) -> tuple[Decision, Decision]:
    assert checked.sibling_by_part is not None
    assert checked.sibling_by_answer is not None
    return checked.sibling_by_part, checked.sibling_by_answer


@pytest.mark.live
def test_the_misjudged_image_is_misjudged_and_its_override_is_recorded(
    checked: PairDecisions,
) -> None:
    """The pair was chosen because the judge gets its first image wrong without help."""
    record = checked.record
    assert record.not_recorded is None, "the judge now has the pair's first image right"
    assert checked.correction is not None
    assert checked.correction.image_id == PAIR.misjudged
    assert (checked.correction.corrected_class, checked.correction.corrected_clause) == (
        record.expected_class,
        record.expected_clause,
    )
    assert record.misjudged_before.truth == (PAIR.truth,)
    assert record.sibling_before.truth == (PAIR.truth,)
    assert record.sibling_before.corrections == ()


@pytest.mark.live
def test_the_override_is_the_line_in_the_siblings_prompt(checked: PairDecisions) -> None:
    """Recall by part puts the correction before the judge, and the decision says so."""
    by_part, _ = _after(checked)
    (region,) = by_part.regions
    assert checked.record.correction is not None
    assert region.corrections == (checked.record.correction,)
    assert by_part.corrected.in_prompt
    assert not by_part.corrected.overridden
    assert region.first_answer is None
    assert region.call is not None
    assert region.call.attempts in (1, 2)


@pytest.mark.live
def test_recall_on_the_answer_asks_again_exactly_when_that_answer_was_corrected_before(
    checked: PairDecisions,
) -> None:
    """A second question only where the sibling's first answer is the one the engineer overrode."""
    _, by_answer = _after(checked)
    (region,) = by_answer.regions
    correction = checked.correction
    assert correction is not None
    overridden = (correction.judged_class, correction.judged_clause)
    if region.first_answer is None:
        assert region.answer is not None
        assert (region.answer.defect_class, region.answer.clause_id) != overridden
        assert region.corrections == ()
        assert not by_answer.corrected.in_prompt
    else:
        assert (region.first_answer.defect_class, region.first_answer.clause_id) == overridden
        assert region.corrections == (checked.record.correction,)
        assert by_answer.corrected.in_prompt


@pytest.mark.live
def test_an_answer_given_with_a_correction_in_view_keeps_the_judges_contract(
    checked: PairDecisions, specification: Specification
) -> None:
    """The class and clause are the part's own, the line has no figure, and code decided."""
    properties = answer_schema(specification, PAIR.category)["properties"]
    assert isinstance(properties, dict)
    for decision in _after(checked):
        (region,) = decision.regions
        assert region.answer is not None, region.reason
        assert region.answer.defect_class in properties["defect_class"]["enum"]
        assert region.answer.clause_id in properties["clause_id"]["enum"]
        assert not any(character.isnumeric() for character in region.answer.reason)
        assert (region.review_cause is not None) == (region.outcome is Outcome.NEEDS_REVIEW)
        assert region.measurement is not None
        if region.rule is not None and region.rule.measured is not None:
            assert region.rule.measured == region.measurement.longest_extent_mm
        if region.outcome is not Outcome.NEEDS_REVIEW:
            assert region.clause is not None
            assert region.clause.heading_id == region.answer.clause_id
            assert region.clause.defect_class == region.answer.defect_class
