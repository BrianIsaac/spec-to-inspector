"""The operator's spot-check: twenty rows of the labelled set, chosen without a hand in it.

The labels are derived, not looked at (the plan's decision 8), so a person
checks a sample against the images. The sample is stratified by part and
defect type: every type gets a row, the rest are allotted in proportion to how
many images carry the type, and within a type the images are taken in the
order of a hash of a fixed seed and the image's path. The choice therefore
repeats exactly and does not depend on anyone's eye, or on the order of the
labelled set.

    uv run python -m spec_to_inspector.bench.spot_check --out eval/spot-check-<date>.md

writes the sheet; it refuses to replace one that exists, since the operator's
ticks are in it.
"""

import hashlib
import textwrap
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final

import typer
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.bench.labels import DEFAULT_LABELS, ClauseLabel, LabelError, read_labels
from spec_to_inspector.bench.mapping import CLAUSE_MAPPING, mapping_row

SPOT_CHECK_ROWS: Final = 20
SPOT_CHECK_SEED: Final = 20261011
IMAGE_ROOT: Final = "data/visa"
"""Where `data fetch` puts VisA, relative to the repository root."""


class SpotCheckRow(BaseModel):
    """One image to check, and the stratum it was drawn for.

    Attributes:
        part: The stratum's part.
        visa_type: The stratum's defect type; the image carries it, perhaps
            among others.
        label: The image's row of the labelled set.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    visa_type: str
    label: ClauseLabel


def allot[K](counts: Mapping[K, int], rows: int) -> dict[K, int]:
    """Share rows among strata in proportion to their sizes, each getting at least one.

    Largest remainders: every stratum has one row to begin with, or its
    proportional share rounded down if that is more; the rows left go one at a
    time to the stratum furthest below its share, the earlier stratum first on
    a tie. No stratum is given more rows than it has images.

    Args:
        counts: The images in each stratum, in the order ties are broken.
        rows: The rows to share.

    Returns:
        The rows per stratum, in the same order.

    Raises:
        ValueError: If there are fewer rows than strata, a stratum is empty,
            or there are fewer images than rows.
    """
    if any(count < 1 for count in counts.values()):
        msg = "a stratum with no image cannot be given a row"
        raise ValueError(msg)
    if rows < len(counts):
        msg = f"{rows} rows cannot cover {len(counts)} strata with one each"
        raise ValueError(msg)
    total = sum(counts.values())
    if total < rows:
        msg = f"{rows} rows were asked of only {total} images"
        raise ValueError(msg)
    shares = {key: rows * count / total for key, count in counts.items()}
    allotted = {key: min(max(1, int(shares[key])), counts[key]) for key in counts}
    while sum(allotted.values()) < rows:
        open_strata = [key for key in counts if allotted[key] < counts[key]]
        furthest = max(open_strata, key=lambda key: shares[key] - allotted[key])
        allotted[furthest] += 1
    while sum(allotted.values()) > rows:
        above = [key for key in counts if allotted[key] > 1]
        nearest = min(above, key=lambda key: shares[key] - allotted[key])
        allotted[nearest] -= 1
    return allotted


def _rank(seed: int, label: ClauseLabel) -> str:
    """Give an image its place in the seeded order.

    Args:
        seed: The seed.
        label: The image's label.

    Returns:
        A digest; images are taken in its ascending order.
    """
    return hashlib.sha256(f"{seed}:{label.visa_image}".encode()).hexdigest()


def choose_rows(
    labels: Sequence[ClauseLabel], *, rows: int = SPOT_CHECK_ROWS, seed: int = SPOT_CHECK_SEED
) -> list[SpotCheckRow]:
    """Choose the images to check, stratified by part and defect type.

    Args:
        labels: The labelled set.
        rows: How many images to choose.
        seed: The seed of the order images are taken in within a stratum.

    Returns:
        The chosen rows, in the mapping table's order of strata. No image is
        chosen twice; the rarest types choose first, so that an image carrying
        a rare type and a common one serves the rare one.

    Raises:
        ValueError: As `allot` raises, or if a stratum's images are used up
            by the rarer strata before it can fill its rows.
    """
    strata = [(row.part, row.visa_type) for row in CLAUSE_MAPPING]
    holding = {
        stratum: sorted(
            (
                label
                for label in labels
                if label.part == stratum[0] and stratum[1] in label.visa_types
            ),
            key=lambda label: _rank(seed, label),
        )
        for stratum in strata
    }
    holding = {stratum: held for stratum, held in holding.items() if held}
    allotted = allot({stratum: len(held) for stratum, held in holding.items()}, rows)

    taken: set[tuple[str, str]] = set()
    chosen: dict[tuple[str, str], list[ClauseLabel]] = {}
    for stratum in sorted(holding, key=lambda stratum: len(holding[stratum])):
        free = [label for label in holding[stratum] if (label.part, label.image_id) not in taken]
        if len(free) < allotted[stratum]:
            part, visa_type = stratum
            msg = f"{part} {visa_type} has {len(free)} images left for {allotted[stratum]} rows"
            raise ValueError(msg)
        chosen[stratum] = free[: allotted[stratum]]
        taken.update((label.part, label.image_id) for label in chosen[stratum])
    return [
        SpotCheckRow(part=stratum[0], visa_type=stratum[1], label=label)
        for stratum in holding
        for label in chosen[stratum]
    ]


def render_spot_check(rows: Sequence[SpotCheckRow], *, checked_on: str) -> str:
    """Lay the sheet out as Markdown, with the operator's columns left blank.

    Args:
        rows: The chosen rows.
        checked_on: The date in the sheet's title, in words.

    Returns:
        The sheet.
    """
    paragraphs = (
        f"For the operator. The plan's decision 8: the labels of `eval/clause_labels.csv` are "
        f"derived from VisA's own annotation through the table of `eval/clause_mapping.md`, and "
        f"{len(rows)} of them are checked by hand against the image. These are the {len(rows)}. "
        "No pane has looked at them: the two right-hand columns are yours.",
        "For each row: open the image (paths are from the repository root, after `uv run "
        "spec-to-inspector data fetch`); see whether it shows the VisA defect type or types "
        "named, and whether the clause named is the one of `specs/pcb-spec.pdf` that covers "
        "that defect. Write `yes` under Agrees, or `no` and what you see under Note. A `no` is "
        "a finding about VisA's annotation or about the mapping table, and either way it goes "
        "in the deck's sentence about the labels.",
        "How the rows were chosen: stratified by part and defect type, one row at least for "
        "each type, the rest in proportion to the number of images that carry the type; within "
        f"a type, in the order of the SHA-256 of `{SPOT_CHECK_SEED}:<image path>`. The command "
        "is `uv run python -m spec_to_inspector.bench.spot_check`, and it gives these rows "
        "every time.",
    )
    lines = [f"# Spot-check of the labelled set, {checked_on}", ""]
    for paragraph in paragraphs:
        lines += [textwrap.fill(paragraph, width=80, break_on_hyphens=False), ""]
    lines += [
        "| # | Part | Image | VisA type(s) | Expected clause(s) | Agrees | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for number, row in enumerate(rows, start=1):
        label = row.label
        clauses = "; ".join(
            mapping_row(label.part, visa_type).heading for visa_type in label.visa_types
        )
        lines.append(
            f"| {number} | {label.part} | `{IMAGE_ROOT}/{label.visa_image}` "
            f"| {', '.join(label.visa_types)} | {clauses} |  |  |"
        )
    lines += [
        "",
        "Checked by: ______________________  Date: ______________",
        "",
    ]
    return "\n".join(lines)


def main(
    out: Annotated[Path, typer.Option("--out", help="Where the sheet is written.")],
    labels: Annotated[
        Path, typer.Option("--labels", help="The labelled set the rows are drawn from.")
    ] = DEFAULT_LABELS,
) -> None:
    """Write the spot-check sheet; an existing sheet is never replaced."""
    if out.exists():
        typer.echo(f"{out} exists and may hold the operator's ticks: not replaced", err=True)
        raise typer.Exit(code=1)
    try:
        rows = choose_rows(read_labels(labels))
    except (LabelError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    today = datetime.now(UTC).astimezone()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_spot_check(rows, checked_on=f"{today.day} {today:%B %Y}"), encoding="utf-8"
    )
    typer.echo(f"{len(rows)} rows for the operator: {out}")


if __name__ == "__main__":
    typer.run(main)
