"""Tests for the checkpoints the protocol names by SHA-256, and the record that holds them."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from spec_to_inspector.bench.checkpoints import (
    CheckpointError,
    CheckpointRecord,
    hold_to_record,
    read_checkpoint_record,
)
from spec_to_inspector.bench.record import FileRef

ROOT = Path(__file__).parents[2]
TRACKED = ROOT / "results" / "stage2" / "checkpoints.json"
MACHINE = {
    "pcb1": "b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855",
    "pcb4": "cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4",
}
LAPTOP = {
    "pcb1": "6250fb1451f4412057e54d1dc676a2a69e3d4d7575ac48d5fad281bb7f9ec187",
    "pcb4": "e932f806135802e8a5ac9586ed75094d690d3529b85646904e84cd901dcddebe",
}


def _entry(sha256: str) -> dict[str, object]:
    return {
        "path": "x/model.ckpt",
        "bytes": 668469863,
        "sha256": sha256,
        "training": "a training",
        "trained_at": "2026-11-06T17:17:44+00:00",
        "fit_seconds": 698.8,
        "image_threshold": 31.3,
        "pixel_threshold": 41.4,
    }


@pytest.fixture
def record() -> CheckpointRecord:
    """Give a record of the machine's two checkpoints, with the laptop's beside them.

    Returns:
        The record.
    """
    return CheckpointRecord.model_validate(
        {
            "read_at": "2026-11-07T03:22:51+00:00",
            "read_how": "sha256sum",
            "rule": "the first training",
            "named": {part: _entry(sha256) for part, sha256 in MACHINE.items()},
            "the_laptops": {part: _entry(sha256) for part, sha256 in LAPTOP.items()},
        }
    )


def test_the_tracked_record_names_the_machines_first_training() -> None:
    """The digests the protocol takes, read on the machine, with what the brief asks beside them."""
    tracked = read_checkpoint_record(TRACKED)

    assert {part: entry.sha256 for part, entry in tracked.named.items()} == MACHINE
    for part, entry in tracked.named.items():
        assert entry.path == f"~/week2/run-1/models/patchcore/{part}/model.ckpt"
        assert entry.bytes == 668469863
        assert "week 2" in entry.training
        assert "run 1" in entry.training
        assert entry.trained_at.startswith("2026-11-06")
    assert tracked.read_at.startswith("2026-11-07")


def test_the_tracked_record_holds_the_laptops_marked_as_the_laptops() -> None:
    """Beside the machine's, so that a digest can be told apart, and never what a run is held to."""
    tracked = read_checkpoint_record(TRACKED)

    assert {part: entry.sha256 for part, entry in tracked.the_laptops.items()} == LAPTOP
    assert all("laptop" in entry.training.lower() for entry in tracked.the_laptops.values())
    assert all(entry.bytes == 668470183 for entry in tracked.the_laptops.values())


def test_the_tracked_record_agrees_with_week_twos_figures() -> None:
    """Its thresholds and fit times are those of the first training, which the protocol takes."""
    tracked = read_checkpoint_record(TRACKED)
    trained = json.loads(
        (ROOT / "results" / "stage2" / "week2" / "run-1" / "anomaly.json").read_text("utf-8")
    )["categories"]

    assert tracked.named.keys() == {"pcb1", "pcb4"}
    for part, entry in tracked.named.items():
        record = trained[part]["record"]
        assert entry.image_threshold == record["thresholds"]["image"]
        assert entry.pixel_threshold == record["thresholds"]["pixel"]
        assert entry.fit_seconds == record["fit_seconds"]
        assert entry.bytes == record["checkpoint_bytes"]
        assert entry.trained_at == record["created_at"]


def test_the_named_checkpoint_passes(record: CheckpointRecord) -> None:
    """Its digest is the one on record: nothing to say."""
    checkpoint = FileRef(path="models/patchcore/pcb1/model.ckpt", sha256=MACHINE["pcb1"])

    hold_to_record(record, "pcb1", checkpoint)


def test_another_checkpoint_is_refused_with_both_digests(record: CheckpointRecord) -> None:
    """Which file, what it holds and what was named, so that the message is enough."""
    checkpoint = FileRef(path="models/x.ckpt", sha256="0" * 64)

    with pytest.raises(CheckpointError) as refused:
        hold_to_record(record, "pcb1", checkpoint)

    message = str(refused.value)
    assert "models/x.ckpt" in message
    assert "0" * 64 in message
    assert MACHINE["pcb1"] in message


def test_the_laptops_checkpoint_is_refused_and_is_called_the_laptops(
    record: CheckpointRecord,
) -> None:
    """The likeliest mistake on the machine, whose `models/` still holds them: it says so."""
    checkpoint = FileRef(path="models/patchcore/pcb1/model.ckpt", sha256=LAPTOP["pcb1"])

    with pytest.raises(CheckpointError, match="the laptop's"):
        hold_to_record(record, "pcb1", checkpoint)


def test_a_part_trained_again_on_another_parts_digest_is_refused(record: CheckpointRecord) -> None:
    """Named is per part: pcb4's digest does not pass for pcb1."""
    checkpoint = FileRef(path="models/x.ckpt", sha256=MACHINE["pcb4"])

    with pytest.raises(CheckpointError, match="pcb1"):
        hold_to_record(record, "pcb1", checkpoint)


def test_a_part_the_record_does_not_name_is_refused(record: CheckpointRecord) -> None:
    """No digest to compare with is not a pass."""
    checkpoint = FileRef(path="models/x.ckpt", sha256=MACHINE["pcb1"])

    with pytest.raises(CheckpointError, match="pcb2"):
        hold_to_record(record, "pcb2", checkpoint)


def test_a_model_with_no_file_is_refused(record: CheckpointRecord) -> None:
    """A model that has no file has no digest, and the void rule cannot be read as met."""
    with pytest.raises(CheckpointError, match="no file"):
        hold_to_record(record, "pcb1", None)


def test_a_record_that_cannot_be_read_says_so(tmp_path: Path) -> None:
    """A missing file and a broken one are each a message, naming the file."""
    with pytest.raises(CheckpointError, match=r"absent\.json"):
        read_checkpoint_record(tmp_path / "absent.json")

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(CheckpointError, match=r"broken\.json"):
        read_checkpoint_record(broken)


@pytest.mark.parametrize("digest", ["short", "A" * 64, "g" * 64, ""])
def test_a_digest_that_is_not_a_sha256_is_refused_when_read(digest: str) -> None:
    """A typed digest in upper case would never match anything: refuse it where it is written."""
    with pytest.raises(ValidationError):
        CheckpointRecord.model_validate(
            {
                "read_at": "x",
                "read_how": "x",
                "rule": "x",
                "named": {"pcb1": _entry(digest)},
                "the_laptops": {},
            }
        )
