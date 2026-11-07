"""Tests for the batch's record: it reads back as it was written, and counts by outcome."""

from pathlib import Path

from spec_to_inspector.batch.record import board_counts
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import judge_run
from tests.batch.batch_fakes import NO_CLAUSE, SCRATCH
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification


def test_the_boards_are_counted_by_outcome_and_the_referred_by_cause(tmp_path: Path) -> None:
    """Every board once; the causes add up to the referred."""
    run = write_run(tmp_path / "judged", {"calm": "good", "cut": "scratch", "odd": "speck"})
    with (
        FakeVlm([SCRATCH, NO_CLAUSE]) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=10) as client,
    ):
        decisions = judge_run(run, specification(), client)

    counts = board_counts(decisions)

    assert (counts.boards, counts.accepted, counts.rejected, counts.referred) == (3, 1, 1, 1)
    assert counts.referred_by_cause == {Cause.NO_CLAUSE_APPLIES.value: 1}
    assert sum(d.outcome is Outcome.REJECT for d in decisions) == counts.rejected
