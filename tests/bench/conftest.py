"""Fixtures shared by the bench's tests: a small set, a plan to run it, and one run's record."""

from pathlib import Path

import pytest

from spec_to_inspector.anomaly.infer import visa_test_items
from spec_to_inspector.bench.record import BenchRecord
from spec_to_inspector.bench.run import BenchPlan, run_bench
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.spec.schema import Specification, read_clause_table
from tests.bench.bench_fakes import (
    REPLIES,
    fake_probes,
    stub_models,
    stub_scoring,
    write_bench_labels,
    write_bench_visa,
)
from tests.judge.fake_vlm import FakeVlm

ROOT = Path(__file__).parents[2]
CLAUSE_TABLE = ROOT / "specs" / "pcb-spec.clauses.json"


def tracked(_pdf: Path) -> Specification:
    """Stand in for the PDF parser: give the tracked clause table.

    Returns:
        The demo specification.
    """
    return read_clause_table(CLAUSE_TABLE)


def run(plan: BenchPlan, server: FakeVlm, **changes: object) -> BenchRecord:
    """Run the bench on a plan against a fake judge, with the stub pipeline.

    Args:
        plan: The plan.
        server: The fake judge.
        **changes: Halves of the pipeline to replace.

    Returns:
        The run's record.
    """
    arguments: dict[str, object] = {
        "parse": tracked,
        "models": stub_models,
        "test_items": visa_test_items,
        "scoring": stub_scoring,
        "probes": fake_probes(),
    } | changes
    with ChatClient(server.url, "fake-vlm", timeout_seconds=10) as client:
        return run_bench(plan, client=client, **arguments)  # pyright: ignore[reportArgumentType]


@pytest.fixture
def plan(tmp_path: Path) -> BenchPlan:
    """Write the small VisA and its labelled set, and plan a run of both parts on them.

    Returns:
        The plan.
    """
    visa = tmp_path / "visa"
    write_bench_visa(visa)
    labels = tmp_path / "eval" / "clause_labels.csv"
    write_bench_labels(visa, tmp_path / "runs", labels)
    return BenchPlan(
        parts=("pcb1", "pcb4"),
        visa_dir=visa,
        runs_dir=tmp_path / "runs",
        spec_pdf=ROOT / "specs" / "pcb-spec.pdf",
        clause_table=CLAUSE_TABLE,
        labels=labels,
        protocol=ROOT / "eval" / "PROTOCOL.md",
        command=("spec-to-inspector", "bench"),
    )


@pytest.fixture
def record(plan: BenchPlan) -> BenchRecord:
    """Run the bench once on the small set, the fake judge answering from its script.

    Returns:
        The run's record.
    """
    with FakeVlm(REPLIES) as server:
        made = run(plan, server)
        assert len(server.requests) == len(REPLIES)
        assert all(request["cache_prompt"] is False for request in server.requests)
    return made
