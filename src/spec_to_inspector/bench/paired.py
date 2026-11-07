"""Figure 10: the paired table and its exact sign test, from a final run and a comparison.

`eval/PROTOCOL-stage2.md`, under "What counts as a move": the pairs are the boards, the runs are the
final run's tracked file and the comparison's second, and a figure is said to have moved only on a
paired, two-sided exact sign test below 0.05 on the 135. The lenient figure is evidence of a change
only if it passes the same test on the 65, under its own name and never pooled.

Nothing here runs a model. Two records and the labelled set they were both scored on give the whole
figure, so it can be counted again at any time; two runs of other boards, other checkpoints or
another labelled set have no pairs and are refused.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.bench.labels import ClauseLabel, read_labels
from spec_to_inspector.bench.observe import Citation, Observation
from spec_to_inspector.bench.record import BenchRecord, FileRef, file_ref, read_record, same_making
from spec_to_inspector.bench.score import cites

PAIRED_NAME: Final = "paired.json"
"""The figure's file, in the comparison's folder beside its record and page."""
THRESHOLD: Final = Fraction(5, 100)
"""The protocol's level. Each comparison is tested on its own at it, with no correction."""
FEWEST_BOARDS_THAT_CAN_REACH_IT: Final = 6
"""With fewer boards differing, no split can reach the threshold: 5 to 0 gives 0.0625."""

Figure = Literal["strict", "lenient"]
"""Which figure a table is of: the 135's, or the 65's under its own name."""


class PairedError(ValueError):
    """Two records cannot be paired as asked; the message says why."""


class SignTest(BaseModel):
    """The paired, two-sided exact sign test on the two "only" counts.

    Attributes:
        only_final: Boards right only on the final run.
        only_comparison: Boards right only on the comparison.
        differing: The two together: the test's N. The ties take no part.
        exact: The p-value as a fraction, as computed.
        p_value: The same as a number.
        below_threshold: Whether it is strictly below 0.05.
        can_reach_threshold: Whether any split of this many boards could be.
    """

    model_config = ConfigDict(frozen=True)

    only_final: int
    only_comparison: int
    differing: int
    exact: str
    p_value: float
    below_threshold: bool
    can_reach_threshold: bool


def sign_test(only_final: int, only_comparison: int) -> SignTest:
    """Run the paired, two-sided exact sign test.

    Under no difference each differing board falls either way with even chance, so the p-value is
    twice the smaller tail of a fair binomial, at most 1. It is counted in exact fractions, so the
    level is never crossed by rounding. No board differing is p = 1: there is nothing to test.

    Args:
        only_final: Boards right only on the final run.
        only_comparison: Boards right only on the comparison.

    Returns:
        The test.

    Raises:
        ValueError: If a count is negative.
    """
    if only_final < 0 or only_comparison < 0:
        msg = f"a count of boards cannot be negative: {only_final} and {only_comparison}"
        raise ValueError(msg)
    differing = only_final + only_comparison
    tail = sum(comb(differing, wins) for wins in range(min(only_final, only_comparison) + 1))
    p = min(Fraction(1), Fraction(2 * tail, 2**differing))
    return SignTest(
        only_final=only_final,
        only_comparison=only_comparison,
        differing=differing,
        exact=str(p),
        p_value=float(p),
        below_threshold=p < THRESHOLD,
        can_reach_threshold=differing >= FEWEST_BOARDS_THAT_CAN_REACH_IT,
    )


class DifferingBoard(BaseModel):
    """A board right on one run and wrong on the other.

    Attributes:
        part: The part.
        image_id: The board.
        expected: The headings that count as right.
        final: What the final run cited, or why it cited nothing.
        comparison: What the comparison cited, or why it cited nothing.
        right_on: Which run was right.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    expected: tuple[str, ...]
    final: str
    comparison: str
    right_on: Literal["the final run", "the comparison"]


class PairedTable(BaseModel):
    """One figure's paired table.

    Attributes:
        figure: Which figure it is of.
        boards: The pairs: 135 for the strict figure and 65 for the lenient, in a whole run.
        both_right: Right on both runs.
        both_wrong: Wrong on both runs.
        only_final: Right only on the final run.
        only_comparison: Right only on the comparison.
        sign_test: The test on the two "only" counts.
        moved: Which way the comparison reads against the final run, where the test is below the
            threshold; None where it is not.
        finding: What the text may say, in the protocol's words.
        differing_boards: The boards the test is made of, board by board.
    """

    model_config = ConfigDict(frozen=True)

    figure: Figure
    boards: int
    both_right: int
    both_wrong: int
    only_final: int
    only_comparison: int
    sign_test: SignTest
    moved: Literal["up", "down"] | None
    finding: str
    differing_boards: tuple[DifferingBoard, ...]


def _strict_finding(test: SignTest, boards: int, moved: Literal["up", "down"] | None) -> str:
    """Say what the text may say of the strict figure.

    Args:
        test: The test.
        boards: The pairs.
        moved: Which way the comparison reads, if the test is below the threshold.

    Returns:
        The sentence.
    """
    if not test.can_reach_threshold:
        return (
            f"{test.differing} of the {boards} boards differ, and with fewer than "
            f"{FEWEST_BOARDS_THAT_CAN_REACH_IT} no split can reach 0.05: no figure separates them."
        )
    if moved is None:
        return f"p = {test.p_value:.4g}, not below 0.05: no figure separates them."
    way = "higher" if moved == "up" else "lower"
    return f"p = {test.p_value:.4g}, below 0.05: the figure moved, the comparison reading {way}."


def _lenient_finding(test: SignTest, moved: Literal["up", "down"] | None) -> str:
    """Say what the text may say of the lenient figure, which never carries the headline.

    Args:
        test: The test.
        moved: Which way the comparison reads, if the test is below the threshold.

    Returns:
        The sentence.
    """
    standing = (
        "It is reported under its own name, is never pooled and offsets nothing of the strict "
        "figure; this is not the primary test."
    )
    if moved is None:
        return (
            f"p = {test.p_value:.4g}: the lenient figure does not pass the test, so it is no "
            f"evidence of a change. {standing}"
        )
    way = "higher" if moved == "up" else "lower"
    return (
        f"p = {test.p_value:.4g}: the lenient figure passes the test, which is evidence of a "
        f"change, the comparison reading {way}. {standing}"
    )


def _cited(observation: Observation) -> str:
    """Say what a run cited on a board, or why it cited nothing.

    Args:
        observation: The board, as the run saw it.

    Returns:
        The heading, or the state of the citation in words.
    """
    if observation.citation is Citation.CITED and observation.cited_heading is not None:
        return observation.cited_heading
    return observation.citation.value


def paired_table(
    figure: Figure,
    labels: Sequence[ClauseLabel],
    final: Sequence[Observation],
    comparison: Sequence[Observation],
) -> PairedTable:
    """Count one figure's paired table.

    A board is right as the scorer counts it: its citation on region 1 is one of its expected
    headings, and no citation is wrong, whatever the reason there is none.

    Args:
        figure: Which figure this is.
        labels: The boards of the figure.
        final: The final run's observations.
        comparison: The comparison's observations.

    Returns:
        The table.

    Raises:
        PairedError: If a run holds no observation of a board.
    """
    runs = (
        {observation.key: observation for observation in final},
        {observation.key: observation for observation in comparison},
    )
    cells = {"both_right": 0, "both_wrong": 0, "only_final": 0, "only_comparison": 0}
    differing: list[DifferingBoard] = []
    for label in labels:
        key = (label.part, label.image_id)
        if key not in runs[0] or key not in runs[1]:
            name = "the comparison" if key in runs[0] else "the final run"
            msg = f"{name} holds no observation of {label.part} {label.image_id}"
            raise PairedError(msg)
        seen_final, seen_comparison = runs[0][key], runs[1][key]
        right = (
            cites(seen_final, label.expected_headings),
            cites(seen_comparison, label.expected_headings),
        )
        if right[0] == right[1]:
            cells["both_right" if right[0] else "both_wrong"] += 1
            continue
        cells["only_final" if right[0] else "only_comparison"] += 1
        differing.append(
            DifferingBoard(
                part=label.part,
                image_id=label.image_id,
                expected=label.expected_headings,
                final=_cited(seen_final),
                comparison=_cited(seen_comparison),
                right_on="the final run" if right[0] else "the comparison",
            )
        )
    test = sign_test(cells["only_final"], cells["only_comparison"])
    moved: Literal["up", "down"] | None = None
    if test.below_threshold:
        moved = "up" if test.only_comparison > test.only_final else "down"
    return PairedTable(
        figure=figure,
        boards=len(labels),
        **cells,
        sign_test=test,
        moved=moved,
        finding=(
            _strict_finding(test, len(labels), moved)
            if figure == "strict"
            else _lenient_finding(test, moved)
        ),
        differing_boards=tuple(differing),
    )


class PairedRecord(BaseModel):
    """Figure 10 for one comparison: what `paired.json` holds.

    Attributes:
        schema_version: The version of this file's layout.
        counted_at: When it was counted, in UTC, ISO 8601.
        final: The final run's record, by its digest.
        comparison: The comparison's record, by its digest.
        labels: The labelled set both were scored on.
        threshold: The level the test is read at.
        correction: That each comparison is tested on its own, uncorrected.
        partial: Whether either run covers less than the whole labelled set. Such a table is not
            the protocol's, whose pairs are the 135 and the 65.
        comparison_is_a_repeat: Whether the comparison's record is of a second run, as the protocol
            pairs. A first run's table is counted and named as such.
        differences: What differs between the two runs' makings, in words: what the comparison is.
        strict: The primary table, over the single-defect boards.
        lenient: The table over the multi-defect boards, not primary.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    counted_at: str
    final: FileRef
    comparison: FileRef
    labels: FileRef
    threshold: float = float(THRESHOLD)
    correction: str = "each comparison is tested on its own at 0.05, with no correction for three"
    partial: bool
    comparison_is_a_repeat: bool
    differences: tuple[str, ...]
    strict: PairedTable
    lenient: PairedTable


def _read(path: Path, what: str) -> BenchRecord:
    """Read one side of the pair.

    Args:
        path: The record.
        what: What it is, for the message.

    Returns:
        The record.

    Raises:
        PairedError: If it cannot be read.
    """
    try:
        return read_record(path)
    except (OSError, ValueError) as error:
        msg = f"{what} {path} cannot be read: {error}"
        raise PairedError(msg) from error


def _same_boards(final: BenchRecord, comparison: BenchRecord, labels: FileRef) -> None:
    """Refuse two runs that do not have the same pairs.

    Args:
        final: The final run.
        comparison: The comparison.
        labels: The labelled set the figure is to be counted from.

    Raises:
        PairedError: If either run is Stage I's, or they differ in what would make their boards or
            their anomaly model another's.
    """
    if final.stage != "II" or comparison.stage != "II":
        msg = "Stage I's figures are history: the protocol runs no test against them"
        raise PairedError(msg)

    def checkpoints(record: BenchRecord) -> dict[str, str | None]:
        return {
            part: run.checkpoint.sha256 if run.checkpoint is not None else None
            for part, run in record.runs.items()
        }

    for name, mine, theirs in (
        ("the parts", final.parts, comparison.parts),
        ("the limit", final.limit, comparison.limit),
        ("the checkpoints", checkpoints(final), checkpoints(comparison)),
        ("the specification", final.specification.pdf.sha256, comparison.specification.pdf.sha256),
        ("the areas per image", final.judge.max_regions, comparison.judge.max_regions),
    ):
        if mine != theirs:
            msg = f"the two runs have no pairs: {name} differ, {mine!r} against {theirs!r}"
            raise PairedError(msg)
    for name, record in (("the final run", final), ("the comparison", comparison)):
        if record.labels.file.sha256 != labels.sha256:
            msg = (
                f"{name} was scored on another labelled set than {labels.path}: "
                f"{record.labels.file.sha256} against {labels.sha256}"
            )
            raise PairedError(msg)


def pair_records(final_path: Path, comparison_path: Path, labels_path: Path) -> PairedRecord:
    """Count figure 10 from two records.

    Args:
        final_path: The final run's record: the protocol's tracked file.
        comparison_path: The comparison's record: its second run.
        labels_path: The labelled set both were scored on.

    Returns:
        The figure.

    Raises:
        PairedError: If either cannot be read, or the two runs have no pairs.
    """
    final = _read(final_path, "the final run's record")
    comparison = _read(comparison_path, "the comparison's record")
    try:
        labels = read_labels(labels_path)
        labels_ref = file_ref(labels_path)
    except (OSError, ValueError) as error:
        msg = f"the labelled set {labels_path} cannot be read: {error}"
        raise PairedError(msg) from error
    _same_boards(final, comparison, labels_ref)
    in_run = {observation.key for observation in final.observations}
    run_labels = [row for row in labels if (row.part, row.image_id) in in_run]
    return PairedRecord(
        counted_at=datetime.now(UTC).isoformat(timespec="seconds"),
        final=file_ref(final_path),
        comparison=file_ref(comparison_path),
        labels=labels_ref,
        partial=final.partial or comparison.partial,
        comparison_is_a_repeat=comparison.repeat is not None,
        differences=tuple(same_making(final, comparison)),
        strict=paired_table(
            "strict",
            [row for row in run_labels if row.single],
            final.observations,
            comparison.observations,
        ),
        lenient=paired_table(
            "lenient",
            [row for row in run_labels if not row.single],
            final.observations,
            comparison.observations,
        ),
    )


def read_paired(path: Path) -> PairedRecord:
    """Read figure 10's file.

    Args:
        path: The file `write_paired` wrote.

    Returns:
        The figure.

    Raises:
        ValueError: If the file is not of this layout.
        OSError: If it cannot be read.
    """
    return PairedRecord.model_validate_json(path.read_text(encoding="utf-8"))


def write_paired(path: Path, paired: PairedRecord) -> None:
    """Write figure 10's file as indented JSON, whole or not at all.

    Args:
        path: The file, created with its directory if absent.
        paired: The figure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(paired.model_dump_json(indent=2) + "\n", encoding="utf-8")
    partial.replace(path)


def figure_beside(record_path: Path) -> PairedRecord | None:
    """Read the figure kept beside a comparison's record, if it was counted from that record.

    A comparison's second run replaces its record, and the page must not then show a table counted
    from the first.

    Args:
        record_path: The comparison's record.

    Returns:
        The figure; None if there is none, it cannot be read, or the record's bytes are no longer
        the ones it was counted from.
    """
    try:
        kept = read_paired(record_path.with_name(PAIRED_NAME))
    except (OSError, ValueError):
        return None
    return kept if file_ref(record_path).sha256 == kept.comparison.sha256 else None
