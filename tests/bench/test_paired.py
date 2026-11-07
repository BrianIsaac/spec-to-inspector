"""Tests for figure 10: the paired table and the sign test, on pairs whose answer is known."""

import itertools
from fractions import Fraction
from pathlib import Path

import pytest

from spec_to_inspector.bench.labels import ClauseLabel, read_labels
from spec_to_inspector.bench.observe import Citation, Observation
from spec_to_inspector.bench.paired import (
    PAIRED_NAME,
    PairedError,
    PairedRecord,
    figure_beside,
    pair_records,
    paired_table,
    read_paired,
    sign_test,
    write_paired,
)
from spec_to_inspector.bench.record import BenchRecord, FileRef, compare, write_record
from tests.bench.bench_fakes import label, seen

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("only_final", "only_comparison", "numerator", "denominator"),
    [
        (0, 0, 1, 1),
        (1, 0, 1, 1),
        (1, 1, 1, 1),
        (5, 0, 2, 32),
        (6, 0, 2, 64),
        (0, 6, 2, 64),
        (5, 1, 14, 64),
        (8, 1, 20, 512),
        (7, 3, 352, 1024),
        (10, 10, 1, 1),
        (9, 3, 299 * 2, 4096),
    ],
)
def test_the_sign_test_gives_the_exact_two_sided_tail_worked_by_hand(
    only_final: int, only_comparison: int, numerator: int, denominator: int
) -> None:
    """Twice the smaller tail of a fair binomial, never above 1: (8, 1) is 2 * (1 + 9) / 2^9."""
    test = sign_test(only_final, only_comparison)

    assert test.exact == str(Fraction(numerator, denominator))
    assert test.p_value == float(Fraction(numerator, denominator))
    assert test.differing == only_final + only_comparison


def test_the_sign_test_agrees_with_an_independent_exact_binomial_test() -> None:
    """Against SciPy's, every split of up to 40 boards, on the value and on the level."""
    stats = pytest.importorskip("scipy.stats")
    for only_final, only_comparison in itertools.product(range(41), repeat=2):
        differing = only_final + only_comparison
        if not 0 < differing <= 40:
            continue
        theirs = stats.binomtest(only_final, differing, 0.5, alternative="two-sided").pvalue
        ours = sign_test(only_final, only_comparison)
        assert ours.p_value == pytest.approx(theirs, abs=1e-12)
        assert ours.below_threshold is bool(theirs < 0.05)


def test_all_ties_cannot_reach_any_level_and_is_not_an_error() -> None:
    """No board differs: there is nothing to test, and p is 1."""
    test = sign_test(0, 0)

    assert (test.p_value, test.below_threshold, test.can_reach_threshold) == (1.0, False, False)


@pytest.mark.parametrize("boards", range(1, 6))
def test_a_one_sided_sweep_below_six_boards_cannot_reach_the_threshold(boards: int) -> None:
    """The protocol's sentence: with fewer than 6 boards differing no split can reach 0.05."""
    for test in (sign_test(boards, 0), sign_test(0, boards)):
        assert test.p_value == float(Fraction(2, 2**boards) if boards > 1 else 1)
        assert not test.below_threshold
        assert not test.can_reach_threshold


@pytest.mark.parametrize("boards", [6, 7, 20, 135])
def test_a_one_sided_sweep_of_six_or_more_is_below_it(boards: int) -> None:
    """All of them one way: 2 / 2^n, which at 6 is 0.03125, the first below 0.05."""
    for test in (sign_test(boards, 0), sign_test(0, boards)):
        assert test.exact == str(Fraction(2, 2**boards))
        assert test.below_threshold
        assert test.can_reach_threshold


@pytest.mark.parametrize(
    ("only_final", "only_comparison", "below"),
    [(6, 0, True), (7, 1, False), (8, 1, True), (9, 2, False), (10, 2, True), (6, 6, False)],
)
def test_the_threshold_is_strictly_below_nought_point_nought_five(
    only_final: int, only_comparison: int, below: bool
) -> None:
    """Either side of it: (7, 1) is 0.0703 and (8, 1) 0.0391, (9, 2) 0.0654 and (10, 2) 0.0386."""
    assert sign_test(only_final, only_comparison).below_threshold is below
    assert sign_test(only_comparison, only_final).below_threshold is below


def test_a_negative_count_is_not_a_count() -> None:
    """A wrong count should say so, not give a p-value."""
    with pytest.raises(ValueError, match="count"):
        sign_test(-1, 2)


def _pairs(
    right_final: list[bool], right_comparison: list[bool]
) -> tuple[list[ClauseLabel], list[Observation], list[Observation]]:
    """Make labelled boards on which each run is right or wrong as asked.

    Args:
        right_final: Per board, whether the final run cites the expected heading.
        right_comparison: The same for the comparison.

    Returns:
        The labels, the final run's observations and the comparison's.
    """
    labels = [label("pcb1", n, "melt", under=("melt",)) for n in range(len(right_final))]

    def run(right: list[bool]) -> list[Observation]:
        return [
            seen("pcb1", f"bad-{n:03d}", "melt" if hit else "scratch", under=("melt",))
            for n, hit in enumerate(right)
        ]

    return labels, run(right_final), run(right_comparison)


def test_the_table_counts_the_four_cells_by_hand() -> None:
    """Two right on both, one wrong on both, three only on the final, one only on the comparison."""
    table = paired_table(
        "strict",
        *_pairs(
            [True, True, False, True, True, True, False],
            [True, True, False, False, False, False, True],
        ),
    )

    assert (table.boards, table.both_right, table.both_wrong) == (7, 2, 1)
    assert (table.only_final, table.only_comparison) == (3, 1)
    assert table.sign_test.exact == str(Fraction(5, 8))
    assert [board.image_id for board in table.differing_boards] == [
        "bad-003",
        "bad-004",
        "bad-005",
        "bad-006",
    ]
    assert table.differing_boards[0].right_on == "the final run"
    assert table.differing_boards[3].right_on == "the comparison"
    assert table.differing_boards[0].expected == ("4.1",)
    assert (table.differing_boards[0].final, table.differing_boards[0].comparison) != (None, None)


def test_a_table_of_all_ties_says_no_figure_separates_them() -> None:
    """Every board right on both: nothing differs, the finding is the protocol's."""
    table = paired_table("strict", *_pairs([True] * 4, [True] * 4))

    assert (table.both_right, table.differing_boards) == (4, ())
    assert "no figure separates them" in table.finding
    assert "fewer than 6" in table.finding
    assert table.moved is None


def test_fewer_than_six_differing_is_the_finding_itself() -> None:
    """Five one way is still no move, and the page says why."""
    table = paired_table("strict", *_pairs([True] * 5, [False] * 5))

    assert table.sign_test.p_value == 0.0625
    assert table.moved is None
    assert "5 of the 5 boards differ" in table.finding
    assert "fewer than 6" in table.finding
    assert "no figure separates them" in table.finding


def test_a_one_sided_sweep_down_is_a_move_down_and_says_which_way() -> None:
    """Six boards the final had and the comparison lost: the figure moved, and down."""
    table = paired_table("strict", *_pairs([True] * 6, [False] * 6))

    assert table.moved == "down"
    assert table.sign_test.p_value == 0.03125
    assert "moved" in table.finding
    assert "lower" in table.finding


def test_a_one_sided_sweep_up_is_a_move_up_and_says_which_way() -> None:
    """Six boards the comparison gained."""
    table = paired_table("strict", *_pairs([False] * 6, [True] * 6))

    assert table.moved == "up"
    assert "higher" in table.finding


def test_enough_boards_split_evenly_are_not_a_move() -> None:
    """Twenty differ and cancel: p is 1, and that is another finding from too few."""
    table = paired_table("strict", *_pairs([True] * 10 + [False] * 10, [False] * 10 + [True] * 10))

    assert table.sign_test.p_value == 1.0
    assert table.moved is None
    assert "no figure separates them" in table.finding
    assert "fewer than 6" not in table.finding


def test_the_lenient_figure_is_evidence_only_never_a_move_of_the_headline() -> None:
    """Its own name, not primary, and it offsets nothing, as the protocol's last section says."""
    passed = paired_table("lenient", *_pairs([False] * 6, [True] * 6))
    failed = paired_table("lenient", *_pairs([False] * 5, [True] * 5))

    assert passed.moved == "up"
    assert "evidence of a change" in passed.finding
    assert "not the primary" in passed.finding
    assert "lenient figure" in passed.finding
    assert "moved" not in passed.finding
    assert "no evidence of a change" in failed.finding
    assert "not the primary" in failed.finding


def test_a_lenient_board_is_right_on_any_of_its_defect_types() -> None:
    """Burnt and dirt expected: either heading counts, on both runs, and neither is a difference."""
    labels = [label("pcb4", 0, "burnt", "dirt", under=("dirt",))]
    final = [seen("pcb4", "bad-000", "burnt", under=("dirt",))]
    comparison = [seen("pcb4", "bad-000", "dirt", under=("dirt",))]

    table = paired_table("lenient", labels, final, comparison)

    assert (table.both_right, table.only_final, table.only_comparison) == (1, 0, 0)


@pytest.mark.parametrize(
    "citation",
    [Citation.NOT_FLAGGED, Citation.NOT_ASKED, Citation.NO_ANSWER, Citation.NO_CLAUSE],
)
def test_no_citation_counts_as_wrong_wherever_a_citation_is_scored(citation: Citation) -> None:
    """The protocol's four ways of having none, and "no clause applies" among them."""
    labels = [label("pcb1", 0, "melt", under=("melt",))]
    final = [seen("pcb1", "bad-000", "melt", under=("melt",))]
    comparison = [seen("pcb1", "bad-000", citation=citation)]

    table = paired_table("strict", labels, final, comparison)

    assert (table.only_final, table.both_wrong) == (1, 0)
    assert table.differing_boards[0].comparison == citation.value


def test_the_real_set_has_the_protocols_two_ns() -> None:
    """The pairs are the boards: 135 and 65 on the tracked set."""
    labels = read_labels(ROOT / "eval" / "clause_labels.csv")

    assert sum(row.single for row in labels) == 135
    assert sum(not row.single for row in labels) == 65


@pytest.fixture
def records(stage2_record: BenchRecord, tmp_path: Path) -> tuple[Path, Path]:
    """Write the small set's run twice, as a final run and a comparison's second run.

    Returns:
        The final run's record and the comparison's.
    """
    final = tmp_path / "final" / "bench.json"
    comparison = tmp_path / "comparison-fp8" / "bench.json"
    write_record(final, stage2_record)
    write_record(comparison, _second(stage2_record))
    return final, comparison


def _second(record: BenchRecord, **changes: object) -> BenchRecord:
    """Make a record read as the second run of a comparison.

    Args:
        record: The run.
        **changes: Other fields to set.

    Returns:
        The copy, with `repeat` filled from the run itself.
    """
    return record.model_copy(update={"repeat": compare(record, record), **changes})


def test_two_records_give_both_tables_with_what_they_are_read_from(
    records: tuple[Path, Path], stage2_plan_labels: Path
) -> None:
    """The small set: 3 single-defect and 1 multi-defect, and two identical runs are all ties."""
    paired = pair_records(*records, stage2_plan_labels)

    assert (paired.strict.boards, paired.lenient.boards) == (3, 1)
    assert paired.strict.only_final == paired.strict.only_comparison == 0
    assert paired.strict.both_right == 2
    assert paired.lenient.both_wrong == 1
    assert paired.final.path == records[0].as_posix()
    assert paired.comparison.path == records[1].as_posix()
    assert len(paired.final.sha256) == 64
    assert paired.labels.path == stage2_plan_labels.as_posix()
    assert paired.comparison_is_a_repeat
    assert paired.threshold == 0.05
    assert not paired.partial


def test_a_comparison_on_its_first_run_is_said_to_be_so(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """The protocol pairs with the comparison's second run: the first is not refused, but named."""
    write_record(records[1], stage2_record)

    assert not pair_records(*records, stage2_plan_labels).comparison_is_a_repeat


def test_what_differs_between_the_two_makings_is_written_down(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """One thing changed is what a comparison is: the record says which."""
    judge = stage2_record.judge.model_copy(update={"reason_pattern": "^other$"})
    write_record(records[1], _second(stage2_record, judge=judge))

    paired = pair_records(*records, stage2_plan_labels)

    assert len(paired.differences) == 1
    assert paired.differences[0].startswith("the reason's pattern")


@pytest.mark.parametrize(
    ("field", "value", "said"),
    [
        ("limit", 3, "the limit"),
        ("parts", ["pcb1"], "the parts"),
    ],
)
def test_runs_of_other_boards_are_refused(
    records: tuple[Path, Path],
    stage2_record: BenchRecord,
    stage2_plan_labels: Path,
    field: str,
    value: object,
    said: str,
) -> None:
    """The pairs are the boards: two runs of different boards have no pairs."""
    write_record(records[1], _second(stage2_record, **{field: value}))

    with pytest.raises(PairedError, match=said):
        pair_records(*records, stage2_plan_labels)


def test_another_checkpoint_is_refused(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """Each comparison changes one thing, and it is never the anomaly model."""
    runs = dict(stage2_record.runs)
    runs["pcb1"] = runs["pcb1"].model_copy(
        update={"checkpoint": FileRef(path="x", sha256="0" * 64)}
    )
    write_record(records[1], _second(stage2_record, runs=runs))

    with pytest.raises(PairedError, match="the checkpoints"):
        pair_records(*records, stage2_plan_labels)


def test_another_labelled_set_is_refused(
    records: tuple[Path, Path], stage2_plan_labels: Path, tmp_path: Path
) -> None:
    """The labels are read from a file: it must be the one both runs were scored on."""
    other = tmp_path / "other.csv"
    other.write_text(stage2_plan_labels.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(PairedError, match="labelled set"):
        pair_records(*records, other)


def test_a_missing_board_is_refused(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """A record that lost a board has fewer pairs than it says: stop, do not quietly drop it."""
    kept = [o for o in stage2_record.observations if o.key != ("pcb1", "bad-000")]
    write_record(records[1], _second(stage2_record, observations=kept))

    with pytest.raises(PairedError, match="bad-000"):
        pair_records(*records, stage2_plan_labels)


def test_stage_one_is_never_a_side_of_the_test(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """The protocol: "no test of this protocol is run against them"."""
    write_record(records[0], stage2_record.model_copy(update={"stage": "I"}))

    with pytest.raises(PairedError, match="Stage I"):
        pair_records(*records, stage2_plan_labels)


def test_a_record_that_cannot_be_read_is_refused(
    records: tuple[Path, Path], stage2_plan_labels: Path, tmp_path: Path
) -> None:
    """A wrong path is a message, not a traceback."""
    with pytest.raises(PairedError, match="missing"):
        pair_records(tmp_path / "missing.json", records[1], stage2_plan_labels)


def test_a_partial_pair_says_it_is_not_the_protocols(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """Both trials of the same boards can be paired, and the record says what that is."""
    write_record(records[0], stage2_record.model_copy(update={"partial": True}))
    write_record(records[1], _second(stage2_record, partial=True))

    assert pair_records(*records, stage2_plan_labels).partial


def test_the_paired_record_is_written_and_read_back(
    records: tuple[Path, Path], stage2_plan_labels: Path, tmp_path: Path
) -> None:
    """It goes to the comparison's folder under a name of its own, whole or not at all."""
    paired = pair_records(*records, stage2_plan_labels)
    path = tmp_path / "comparison-fp8" / PAIRED_NAME

    write_paired(path, paired)

    assert read_paired(path) == paired
    assert isinstance(read_paired(path), PairedRecord)
    assert list(path.parent.glob(f".{PAIRED_NAME}*")) == []


def test_the_figure_beside_a_record_is_read_only_while_that_record_stands(
    records: tuple[Path, Path], stage2_record: BenchRecord, stage2_plan_labels: Path
) -> None:
    """A second run replaces the record, and the table counted from the first must not show."""
    comparison = records[1]
    assert figure_beside(comparison) is None

    write_paired(comparison.with_name(PAIRED_NAME), pair_records(*records, stage2_plan_labels))
    assert figure_beside(comparison) is not None

    write_record(comparison, _second(stage2_record, measured_on="another day"))
    assert figure_beside(comparison) is None


def test_a_file_that_is_no_figure_beside_a_record_is_left_out(records: tuple[Path, Path]) -> None:
    """It says nothing of the record, so the page goes without."""
    records[1].with_name(PAIRED_NAME).write_text("not a figure", encoding="utf-8")

    assert figure_beside(records[1]) is None
