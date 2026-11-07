"""The checkpoints the Stage II protocol names by SHA-256, and the void rule's last clause.

`eval/PROTOCOL-stage2.md` takes each part's checkpoint from week 2's record by its SHA-256, the
first training where there are two, and voids a run whose checkpoint is not that one. Week 2's
record held no digest, so they are kept in a file of their own, `results/stage2/checkpoints.json`:
read on the machine, with the path, the size, the training and its date. The laptop's two stand
beside them so a digest can be told apart; a run is never held to them.
"""

from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, StringConstraints

from spec_to_inspector.bench.record import FileRef

DEFAULT_RECORD: Final = Path("results/stage2/checkpoints.json")

_Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class CheckpointError(ValueError):
    """A checkpoint is not the one named, or the record of them cannot be read."""


class CheckpointEntry(BaseModel):
    """One checkpoint on record.

    Attributes:
        path: Where it was read, on the machine that holds it.
        bytes: Its size.
        sha256: The SHA-256 of its bytes.
        training: Which training made it, in words.
        trained_at: When, in UTC, as its own training record says.
        fit_seconds: The fit time its training recorded.
        image_threshold: The raw score above which a board is flagged.
        pixel_threshold: The raw score above which a pixel is.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    bytes: int
    sha256: _Sha256
    training: str
    trained_at: str
    fit_seconds: float
    image_threshold: float
    pixel_threshold: float


class CheckpointRecord(BaseModel):
    """What `results/stage2/checkpoints.json` holds.

    Attributes:
        read_at: When the digests were read, in UTC.
        read_how: How they were read, and where.
        rule: Why these checkpoints and not others.
        named: Per part, the checkpoint a Stage II run is held to.
        the_laptops: Per part, the laptop's, to tell a digest apart; a run is never held to these.
    """

    model_config = ConfigDict(frozen=True)

    read_at: str
    read_how: str
    rule: str
    named: dict[str, CheckpointEntry]
    the_laptops: dict[str, CheckpointEntry]


def read_checkpoint_record(path: Path) -> CheckpointRecord:
    """Read the record of the checkpoints.

    Args:
        path: The file.

    Returns:
        The record.

    Raises:
        CheckpointError: If it cannot be read or is not of this layout.
    """
    try:
        return CheckpointRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        msg = f"the record of the checkpoints' digests, {path}, cannot be read: {error}"
        raise CheckpointError(msg) from error


def hold_to_record(record: CheckpointRecord, part: str, checkpoint: FileRef | None) -> None:
    """Hold the checkpoint a part's model was loaded from to the one named.

    Args:
        record: The record of the checkpoints.
        part: The part.
        checkpoint: The file the model was loaded from, by its digest; None if it has no file.

    Raises:
        CheckpointError: If the part has no checkpoint named, the model has no file to compare, or
            the file's digest is not the named one.
    """
    named = record.named.get(part)
    if named is None:
        msg = f"the record of the checkpoints names none for {part}, so it cannot be held to one"
        raise CheckpointError(msg)
    if checkpoint is None:
        msg = f"{part}'s model has no file, so its digest cannot be compared with {named.sha256}"
        raise CheckpointError(msg)
    if checkpoint.sha256 == named.sha256:
        return
    laptops = record.the_laptops.get(part)
    whose = (
        ", which is the laptop's"
        if laptops is not None and laptops.sha256 == checkpoint.sha256
        else ""
    )
    msg = (
        f"{part}'s checkpoint {checkpoint.path} has SHA-256 {checkpoint.sha256}{whose}, and the "
        f"protocol names {named.sha256}, {named.path}"
    )
    raise CheckpointError(msg)
