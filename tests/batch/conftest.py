"""Fixtures shared by the batch's tests: a repository in miniature, on the machine."""

import json
import shutil
from pathlib import Path

import pytest

from spec_to_inspector import cli
from spec_to_inspector.anomaly.infer import visa_test_items
from spec_to_inspector.batch import memory as batch_memory
from spec_to_inspector.bench import run as benching
from spec_to_inspector.settings import Settings
from tests.bench.bench_fakes import (
    machine_probes,
    stub_models_with_files,
    stub_scoring,
    write_bench_visa,
    write_checkpoint_record,
)
from tests.bench.conftest import tracked

ROOT = Path(__file__).parents[2]
DIGESTS = Path("results/stage2/checkpoints.json")
PCB1_REPLIES = (
    json.dumps({"reason": "a lump of solder", "defect_class": "melt", "clause_id": "4.1"}),
)
"""The fake judge's answer to pcb1's flagged area."""
PCB4_REPLIES = (
    json.dumps({"reason": "a small dark speck", "defect_class": "dirt", "clause_id": "5.1"}),
    json.dumps({"reason": "a long bright line", "defect_class": "scratch", "clause_id": "5.6"}),
    json.dumps({"reason": "nothing but the fixture", "defect_class": None, "clause_id": None}),
    json.dumps({"reason": "a charred component", "defect_class": "burnt", "clause_id": "5.7"}),
)
"""The fake judge's answers to pcb4's flagged areas, in the split's order."""


@pytest.fixture
def machine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Lay out a repository in miniature on the machine: an Intel card, its server in a container.

    Returns:
        The working directory.
    """
    monkeypatch.chdir(tmp_path)
    for name in ("DATA", "MODELS", "RUNS"):
        monkeypatch.setenv(f"SPEC_TO_INSPECTOR_{name}_DIR", str(tmp_path / name.lower()))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_MODEL", "fake-vlm")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DEVICE", "xpu")
    monkeypatch.setattr(cli.out, "width", 400)
    monkeypatch.setattr(cli.err, "width", 400)
    monkeypatch.setattr(batch_memory, "BATCH_INTERVAL_SECONDS", 0.01)
    write_bench_visa(tmp_path / "data" / "visa")
    Path("eval").mkdir()
    for protocol in (ROOT / "eval").glob("PROTOCOL*.md"):
        shutil.copy(protocol, Path("eval") / protocol.name)
    Path("specs").mkdir()
    for name in ("pcb-spec.pdf", "pcb-spec.clauses.json"):
        shutil.copy(ROOT / "specs" / name, Path("specs") / name)
    write_checkpoint_record(DIGESTS)

    def pipeline(_settings: Settings) -> benching.Pipeline:
        return benching.Pipeline(
            parse=tracked,
            models=stub_models_with_files(tmp_path / "models"),
            test_items=visa_test_items,
            scoring=stub_scoring,
        )

    monkeypatch.setattr(benching, "device_probes", lambda _settings: machine_probes())
    monkeypatch.setattr(benching, "laptop_pipeline", pipeline)
    return tmp_path
