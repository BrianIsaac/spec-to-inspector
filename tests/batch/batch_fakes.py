"""Fakes for the batch's tests: a judged run on disk, with one board of each outcome."""

import json
from pathlib import Path

from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.inspect import judge_run
from spec_to_inspector.spec.schema import Specification
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run

SCRATCH = json.dumps(
    {
        "reason": "a thin bright line scored across the board face",
        "defect_class": "scratch",
        "clause_id": "4.1",
    }
)
NO_CLAUSE = json.dumps(
    {"reason": "nothing but the fixture is visible here", "defect_class": None, "clause_id": None}
)


def judged_run(root: Path, specification: Specification) -> Path:
    """Write a run with an accepted, a rejected and a referred board, and judge it.

    Args:
        root: A temporary directory.
        specification: The specification the boards are judged against.

    Returns:
        The run's directory.
    """
    run = write_run(root, {"calm": "good", "cut": "scratch", "odd": "speck"})
    with (
        FakeVlm([SCRATCH, NO_CLAUSE]) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=10) as client,
    ):
        judge_run(run, specification, client)
    return run
