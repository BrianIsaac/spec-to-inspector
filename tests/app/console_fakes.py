"""A small world for the console's tests: a judged run, a trained model and a specification.

The run is the judge's own fake (`tests.judge.run_fakes`), written by the real
inference writer and judged by the real judge against a scripted VLM, so the
console reads files of exactly the shape the pipeline leaves. Part `pcb9`,
batch `batch`: two boards accepted, two rejected, one referred, one not judged.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.inspect import judge_run
from spec_to_inspector.spec.schema import Specification, write_clause_table
from tests.anomaly.records_fakes import train_record
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import CATEGORY, Kind, write_run
from tests.spec.spec_fakes import specification

BATCH: Final = "batch"
MODEL_SENTENCE: Final = "a thin bright line scored across the board face"
REPLY: Final = json.dumps({"reason": MODEL_SENTENCE, "defect_class": "scratch", "clause_id": "4.1"})
BOARDS: Final[dict[str, Kind]] = {
    "good": "good",
    "speck": "speck",
    "scratch": "scratch",
    "two": "two",
    "peak": "peak",
    "late": "scratch",
}
JUDGED: Final = ("good", "speck", "scratch", "two", "peak")


@dataclass(frozen=True)
class World:
    """Where the fake world's files are.

    Attributes:
        root: The temporary directory holding everything.
        runs_dir: The runs directory, holding `pcb9/batch`.
        run: The run's directory.
        models_dir: The models directory, holding `patchcore/pcb9/train.json`.
        spec_path: The fake specification's clause table.
        specification: The fake specification.
    """

    root: Path
    runs_dir: Path
    run: Path
    models_dir: Path
    spec_path: Path
    specification: Specification


def write_world(root: Path) -> World:
    """Write the run, judge five of its six boards, and add a model record and a clause table.

    Args:
        root: A temporary directory.

    Returns:
        Where everything is.
    """
    spec = specification()
    run = write_run(root, BOARDS)
    with (
        FakeVlm(default=REPLY) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
    ):
        judge_run(run, spec, client, image_ids=JUDGED)

    models_dir = root / "models"
    record = models_dir / "patchcore" / CATEGORY / "train.json"
    record.parent.mkdir(parents=True)
    record.write_text(train_record(CATEGORY).model_dump_json(indent=2), encoding="utf-8")

    spec_path = root / "spec.clauses.json"
    write_clause_table(spec, spec_path)
    return World(
        root=root,
        runs_dir=root / "runs",
        run=run,
        models_dir=models_dir,
        spec_path=spec_path,
        specification=spec,
    )
