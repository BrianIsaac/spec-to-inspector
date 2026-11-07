"""The corrections comparison's store, built from the tracked record and the labelled set.

`eval/PROTOCOL-stage2-addition-corrections-2026-11-07.md` declares it. For each part ten
single-defect boards are drawn by a seeded rule, a generator of the part's own over the boards
sorted by image id. A drawn board's correction takes its judged half from what the final run's
tracked record answered and its corrected half from the label's region columns, and its note is the
corrected clause's heading as the clause table prints it. Nothing is written by hand.

A drawn board holds no correction where the final already answered as the label does, since the
store refuses an override that repeats the judge, or where the label's region columns are empty, as
they are when region 1 lies off the labelled defect. The addition's dated line says why. Such a
board is still drawn, so it stays out of the comparison's figures with the rest.

The rows go in in the draw's order, and each is stamped with the final run's end rather than the
clock, so the same files and the same SQLite build the same bytes:

    uv run python -m spec_to_inspector.corrections.declared_store

It writes `results/stage2/comparison-corrections/store.sqlite3` and `store.json` beside it, which
says what became of each board and holds every file it was built from by digest.
"""

import random
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated, Final

import typer
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.bench.labels import ClauseLabel, Region1, read_labels
from spec_to_inspector.bench.observe import Observation
from spec_to_inspector.bench.record import FileRef, file_ref, read_record
from spec_to_inspector.corrections.store import MAX_RECALL, CorrectionStore, Override
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

SEED: Final = 20261107
BOARDS_PER_PART: Final = 10
FIRST_REGION: Final = 1
"""The figures read region 1, the most anomalous area, so a correction is of its answer."""
SCRIPT: Final = "src/spec_to_inspector/corrections/declared_store.py"

DEFAULT_FINAL: Final = Path("results/stage2/final/bench.json")
DEFAULT_LABELS: Final = Path("eval/clause_labels.csv")
DEFAULT_CLAUSES: Final = Path("specs/pcb-spec.clauses.json")
DEFAULT_STORE: Final = Path("results/stage2/comparison-corrections/store.sqlite3")

NOTHING_TO_CORRECT: Final = "the final run already answered as the label does"
NOTHING_TO_CORRECT_TO: Final = "the label's region columns are empty, so it names no clause"


class DeclaredStoreError(ValueError):
    """The store cannot be built from these files; the message says why."""


class LeftOut(BaseModel):
    """A drawn board that holds no correction.

    Attributes:
        part: The part.
        image_id: The board.
        reason: Why it holds none.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    reason: str


class Declared(BaseModel):
    """What the draw gives before anything is stored.

    Attributes:
        drawn: Each part's boards, in the draw's order.
        overrides: The corrections, in the order they go in.
        left_out: The drawn boards that hold none.
    """

    model_config = ConfigDict(frozen=True)

    drawn: dict[str, tuple[str, ...]]
    overrides: tuple[Override, ...]
    left_out: tuple[LeftOut, ...]


class Recall(BaseModel):
    """The recall the store is built for, the settings' default.

    Attributes:
        strategy: When the corrections are put before the judge.
        limit: The most that stand in one prompt.
    """

    model_config = ConfigDict(frozen=True)

    strategy: str
    limit: int


class StoreManifest(BaseModel):
    """What `store.json` holds.

    Attributes:
        seed: The seed of each part's generator.
        boards_per_part: How many boards each part draws.
        recall: The recall the store is built for.
        final: The final run's tracked record, the judged half.
        labels: The labelled set, the draw and the corrected half.
        clause_table: The clause table, the note.
        script: This module, by its digest.
        sqlite: The SQLite that wrote the file, whose build its bytes depend on.
        store: The store's file.
        corrections: Rows the store holds.
        drawn: Each part's boards, in the draw's order: the boards the comparison leaves out of its
            figures.
        left_out: The drawn boards that hold no correction, and why.
    """

    model_config = ConfigDict(frozen=True)

    seed: int
    boards_per_part: int
    recall: Recall
    final: FileRef
    labels: FileRef
    clause_table: FileRef
    script: FileRef
    sqlite: str
    store: FileRef
    corrections: int
    drawn: dict[str, tuple[str, ...]]
    left_out: tuple[LeftOut, ...]


def draw_boards(
    labels: Sequence[ClauseLabel], *, per_part: int = BOARDS_PER_PART
) -> dict[str, tuple[str, ...]]:
    """Draw each part's boards by the addition's rule.

    Args:
        labels: The labelled set.
        per_part: How many boards a part draws.

    Returns:
        Each part's boards, in the draw's order and the labelled set's order of parts.

    Raises:
        DeclaredStoreError: If a part has too few single-defect boards.
    """
    parts = dict.fromkeys(label.part for label in labels)
    drawn: dict[str, tuple[str, ...]] = {}
    for part in parts:
        boards = sorted(label.image_id for label in labels if label.part == part and label.single)
        if len(boards) < per_part:
            msg = f"{part} has {len(boards)} single-defect board(s), and the rule draws {per_part}"
            raise DeclaredStoreError(msg)
        drawn[part] = tuple(random.Random(SEED).sample(boards, per_part))  # noqa: S311 - the protocol's own, reproducible draw
    return drawn


def _heading_title(specification: Specification, part: str, heading: str, named: str) -> str:
    """Read a corrected clause's heading from the clause table.

    Args:
        specification: The clause table.
        part: The part.
        heading: The numbered heading.
        named: The class the label names under it.

    Returns:
        The heading as the table prints it.

    Raises:
        DeclaredStoreError: If the part has no such heading or holds another class under it.
    """
    for clause in specification.clauses:
        if clause.category == part and clause.heading_id == heading:
            if clause.defect_class != named:
                msg = f"clause {heading} is for '{clause.defect_class}', not '{named}'"
                raise DeclaredStoreError(msg)
            return clause.title
    msg = f"part {part} has no clause {heading}"
    raise DeclaredStoreError(msg)


def declared_corrections(
    labels: Sequence[ClauseLabel],
    final: Sequence[Observation],
    specification: Specification,
) -> Declared:
    """Make the corrections from the final run's answers and the labels, in the draw's order.

    Args:
        labels: The labelled set.
        final: The final run's observations.
        specification: The clause table.

    Returns:
        The draw, its corrections and the boards that hold none.

    Raises:
        DeclaredStoreError: If the final holds no line for a drawn board, or a label's class is not
            its heading's.
    """
    drawn = draw_boards(labels)
    rows = {(label.part, label.image_id): label for label in labels}
    lines = {observation.key: observation for observation in final}
    overrides: list[Override] = []
    left_out: list[LeftOut] = []
    for part, boards in drawn.items():
        for image_id in boards:
            label = rows[(part, image_id)]
            seen = lines.get((part, image_id))
            if seen is None:
                msg = f"the final run's record has no line for {part} {image_id}"
                raise DeclaredStoreError(msg)
            if label.region1 is not Region1.ONE_TYPE:
                left_out.append(LeftOut(part=part, image_id=image_id, reason=NOTHING_TO_CORRECT_TO))
                continue
            corrected = (label.region1_types[0], label.region1_headings[0])
            if (seen.cited_class, seen.cited_heading) == corrected:
                left_out.append(LeftOut(part=part, image_id=image_id, reason=NOTHING_TO_CORRECT))
                continue
            overrides.append(
                Override(
                    category=part,
                    image_id=image_id,
                    region_index=FIRST_REGION,
                    judged_class=seen.cited_class,
                    judged_clause=seen.cited_heading,
                    judged_outcome=seen.areas[0].outcome,
                    judged_reason=seen.sentence,
                    corrected_class=corrected[0],
                    corrected_clause=corrected[1],
                    note=_heading_title(specification, part, corrected[1], corrected[0]),
                )
            )
    return Declared(drawn=drawn, overrides=tuple(overrides), left_out=tuple(left_out))


def build_store(
    final_path: Path, labels_path: Path, clauses_path: Path, out: Path
) -> StoreManifest:
    """Build the store and its manifest, each whole or not at all.

    Args:
        final_path: The final run's tracked record.
        labels_path: The labelled set.
        clauses_path: The clause table.
        out: The store's file; the manifest goes beside it with the suffix `.json`.

    Returns:
        The manifest as written.

    Raises:
        DeclaredStoreError: If the corrections cannot be made from these files.
    """
    final = read_record(final_path)
    declared = declared_corrections(
        read_labels(labels_path), final.observations, read_clause_table(clauses_path)
    )
    made_at = datetime.fromisoformat(final.measured_at)
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f".{out.name}.partial")
    partial.unlink(missing_ok=True)
    store = CorrectionStore(partial)
    for override in declared.overrides:
        store.record(override, at=made_at)
    partial.replace(out)

    manifest = StoreManifest(
        seed=SEED,
        boards_per_part=BOARDS_PER_PART,
        recall=Recall(
            strategy=Settings.model_fields["corrections_recall"].default, limit=MAX_RECALL
        ),
        final=file_ref(final_path),
        labels=file_ref(labels_path),
        clause_table=file_ref(clauses_path),
        script=FileRef(path=SCRIPT, sha256=file_ref(Path(__file__)).sha256),
        sqlite=sqlite3.sqlite_version,
        store=file_ref(out),
        corrections=CorrectionStore(out).count(),
        drawn=declared.drawn,
        left_out=declared.left_out,
    )
    out.with_suffix(".json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def main(
    final: Annotated[
        Path, typer.Option("--final", help="The final run's tracked record.")
    ] = DEFAULT_FINAL,
    labels: Annotated[Path, typer.Option("--labels", help="The labelled set.")] = DEFAULT_LABELS,
    clauses: Annotated[Path, typer.Option("--spec", help="The clause table.")] = DEFAULT_CLAUSES,
    out: Annotated[Path, typer.Option("--out", help="The store's file.")] = DEFAULT_STORE,
) -> None:
    """Build the corrections comparison's store from the tracked files."""
    try:
        manifest = build_store(final, labels, clauses, out)
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"{out}: {manifest.corrections} corrections of the {BOARDS_PER_PART} boards each of "
        f"{', '.join(manifest.drawn)} draws; SHA-256 {manifest.store.sha256}"
    )


if __name__ == "__main__":
    typer.run(main)
