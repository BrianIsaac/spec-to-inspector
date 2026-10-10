"""Tests for the scorer: the protocol's figures on hand-made labels and observations."""

import pytest

from spec_to_inspector.bench.observe import Area, Citation
from spec_to_inspector.bench.score import ScoreError, score
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.disposition import Outcome
from tests.bench.bench_fakes import label, seen

REVIEW = Outcome.NEEDS_REVIEW

LABELS = [
    label("pcb1", 0, "melt", under=("melt",)),
    label("pcb1", 1, "melt", under=()),
    label("pcb1", 2, "scratch", under=("scratch",)),
    label("pcb1", 3, "bent", under=None),
    label("pcb4", 0, "burnt", under=("burnt",)),
    label("pcb4", 1, "missing", under=("missing",)),
    label("pcb4", 2, "burnt", "dirt", under=("dirt",)),
    label("pcb4", 3, "scratch", "extra", under=("scratch", "extra")),
    label("pcb4", 4, "missing", "dirt", under=("missing",)),
]

OBSERVATIONS = [
    seen("pcb1", "bad-000", "melt", under=("melt",), row="4.1"),
    seen("pcb1", "bad-001", "melt", under=(), row="4.1"),
    seen(
        "pcb1",
        "bad-002",
        "scratch",
        under=("scratch",),
        outcome=Outcome.ACCEPT,
        row="4.2.2",
        more_areas=(
            Area(
                index=2,
                outcome=REVIEW,
                review_cause=Cause.NO_CLAUSE_APPLIES,
                asked=True,
                seconds=3.0,
                attempts=1,
            ),
        ),
    ),
    seen("pcb1", "bad-003", citation=Citation.NOT_FLAGGED),
    seen(
        "pcb4",
        "bad-000",
        "damage",
        under=("burnt",),
        row="5.5",
        named="burnt",
        outcome=REVIEW,
        cause=Cause.CLASS_MISMATCH,
    ),
    seen("pcb4", "bad-001", under=("missing",), outcome=REVIEW, cause=Cause.NO_CLAUSE_APPLIES),
    seen("pcb4", "bad-002", "burnt", under=("dirt",), row="5.7"),
    seen("pcb4", "bad-003", "dirt", under=("scratch", "extra"), row="5.1.1"),
    seen("pcb4", "bad-004", "missing", under=("missing",), row="5.2"),
    seen("pcb1", "good-0001", citation=Citation.NOT_FLAGGED, kind="good"),
    seen("pcb1", "good-0002", "melt", kind="good", row="4.1"),
    seen("pcb4", "good-0001", kind="good", outcome=REVIEW, cause=Cause.NO_CLAUSE_APPLIES),
    seen("pcb4", "good-0002", citation=Citation.NOT_FLAGGED, kind="good"),
    seen("pcb4", "good-0003", citation=Citation.NOT_FLAGGED, kind="good"),
]


def test_the_headline_is_strict_on_the_single_defect_images_and_counts_no_citation_as_wrong() -> (
    None
):
    """Six single-defect images: three cite their heading; unflagged and uncited are wrong."""
    headline = score(LABELS, OBSERVATIONS).headline

    assert (headline.strict.all.count, headline.strict.all.n) == (3, 6)
    assert headline.strict.all.rate == pytest.approx(0.5)
    assert headline.strict.all.low == pytest.approx(0.1876, abs=5e-5)
    by_part = {part: (p.count, p.n) for part, p in headline.strict.by_part.items()}
    assert by_part == {"pcb1": (3, 4), "pcb4": (0, 2)}


def test_the_anomaly_models_ceiling_and_the_judges_own_share_stand_beside_it() -> None:
    """Flagged, region 1 on the defect, and the accuracy given each."""
    headline = score(LABELS, OBSERVATIONS).headline

    assert (headline.flagged.all.count, headline.flagged.all.n) == (5, 6)
    assert (headline.on_defect.all.count, headline.on_defect.all.n) == (4, 6)
    assert (headline.strict_given_flagged.all.count, headline.strict_given_flagged.all.n) == (3, 5)
    assert (headline.strict_given_on_defect.all.count, headline.strict_given_on_defect.all.n) == (
        2,
        4,
    )


def test_the_row_code_applied_is_reported_for_the_correct_citations_only() -> None:
    """The row is a measurement's outcome: counted beside the figure, never scored."""
    headline = score(LABELS, OBSERVATIONS).headline

    assert headline.rows_applied == {"4.1": 2, "4.2.2": 1}
    assert headline.region1_outcomes == {"reject": 2, "accept": 1}


def test_the_lenient_figure_takes_any_of_the_images_types_and_stays_apart() -> None:
    """Three multi-defect images: citing any expected heading counts; a third type does not."""
    scores = score(LABELS, OBSERVATIONS)

    assert (scores.lenient.all.count, scores.lenient.all.n) == (2, 3)
    assert set(scores.lenient.by_part) == {"pcb1", "pcb4"}
    assert scores.lenient.by_part["pcb1"].n == 0
    assert scores.lenient.by_part["pcb1"].rate is None


def test_the_per_region_figure_scores_region_one_against_the_one_type_under_it() -> None:
    """Six images have one type under region 1; a multi-defect image is scored exactly."""
    per_region = score(LABELS, OBSERVATIONS).per_region

    assert (per_region.all.count, per_region.all.n) == (3, 6)
    assert (per_region.by_part["pcb4"].count, per_region.by_part["pcb4"].n) == (1, 4)


def test_the_confusion_table_is_expected_type_against_the_cited_headings_type() -> None:
    """Rows are VisA's type; columns the cited heading's type or why there is none."""
    scores = score(LABELS, OBSERVATIONS)

    assert scores.confusion_single["pcb1"] == {
        "melt": {"melt": 2},
        "scratch": {"scratch": 1},
        "bent": {"not flagged": 1},
    }
    assert scores.confusion_single["pcb4"] == {
        "burnt": {"damage": 1},
        "missing": {"no clause applies": 1},
    }
    assert scores.confusion_region["pcb4"]["dirt"] == {"burnt": 1}
    assert scores.class_not_of_heading == 1


def test_needs_review_is_split_by_cause_at_both_levels_on_the_anomalous_boards() -> None:
    """Nine boards, nine areas judged: boards and areas are counted apart."""
    anomalous = score(LABELS, OBSERVATIONS).anomalous

    assert anomalous.boards == 9
    assert anomalous.not_flagged == 1
    assert anomalous.board_outcomes == {"reject": 5, "accept": 1, "needs review": 2}
    assert anomalous.board_review_causes == {"class mismatch": 1, "no clause applies": 1}
    assert (anomalous.board_needs_review.count, anomalous.board_needs_review.n) == (2, 9)
    assert anomalous.areas == 9
    assert anomalous.area_outcomes == {"reject": 5, "accept": 1, "needs review": 3}
    assert anomalous.area_review_causes == {"class mismatch": 1, "no clause applies": 2}


def test_false_alarms_on_good_boards_are_counted_apart_from_the_accuracy() -> None:
    """Five good boards: two flagged, one rejected on a cited clause, one referred."""
    good = score(LABELS, OBSERVATIONS).good

    assert (good.all.flagged.count, good.all.flagged.n) == (2, 5)
    assert (good.all.rejected.count, good.all.rejected.n) == (1, 5)
    assert (good.all.referred.count, good.all.accepted_after_judging.count) == (1, 0)
    assert good.all.citations == {"4.1": 1, "no clause applies": 1}
    assert good.by_part["pcb4"].flagged.n == 3
    assert good.all.dispositions.board_review_causes == {"no clause applies": 1}


def test_a_labelled_image_the_run_did_not_see_is_an_error() -> None:
    """A figure over fewer images than its N would be a different figure."""
    with pytest.raises(ScoreError, match="pcb4 bad-004"):
        score(LABELS, OBSERVATIONS[:8] + OBSERVATIONS[9:])


def test_region_truth_that_is_not_the_runs_is_named() -> None:
    """The labelled set's region columns must be what this run's regions lie on."""
    moved = [seen("pcb1", "bad-000", "melt", under=(), row="4.1"), *OBSERVATIONS[1:]]
    assert score(LABELS, moved).stale_region_truth == ["pcb1 bad-000"]
    assert score(LABELS, OBSERVATIONS).stale_region_truth == []
