"""What the `inspect` verb prints: one line per board, and a line for the batch."""

from collections.abc import Sequence
from pathlib import Path

from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.disposition import Outcome


def verdict_line(decision: Decision) -> str:
    """Give a board's verdict on one line.

    Args:
        decision: The board's decision.

    Returns:
        The image, the outcome, the clause applied with its page if there is
        one, and the reason.
    """
    clause = decision.clause
    cited = "" if clause is None else f", clause {clause.id} {clause.title} (page {clause.page})"
    return f"{decision.image_id}: {decision.outcome.value}{cited}: {decision.reason}"


def summary_line(decisions: Sequence[Decision], run_directory: Path) -> str:
    """Give the batch's counts on one line.

    Args:
        decisions: The decisions made.
        run_directory: Where each image's `decision.json` was written.

    Returns:
        How many boards were accepted, rejected and referred, and where the
        decisions are.
    """
    counts = {outcome: sum(d.outcome is outcome for d in decisions) for outcome in Outcome}
    images = "1 image" if len(decisions) == 1 else f"{len(decisions)} images"
    return (
        f"{images}: "
        + ", ".join(f"{count} {outcome.value}" for outcome, count in counts.items())
        + f". Decisions: {run_directory}"
    )


def unreachable(decisions: Sequence[Decision]) -> int:
    """Count the boards referred because the judge could not be asked.

    Args:
        decisions: The decisions made.

    Returns:
        How many boards have a region the server failed to answer for,
        whether or not that region is the one the board's outcome rests on.
    """
    return sum(
        any(region.review_cause is Cause.SERVER_UNAVAILABLE for region in decision.regions)
        for decision in decisions
    )
