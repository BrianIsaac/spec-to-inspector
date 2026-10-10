"""The labelled set: every anomalous test image of the two parts, with the clause expected.

Nothing here is labelled by hand. Each row is one line of VisA's
`image_anno.csv`, which names the image's defect types, mapped to the
specification's numbered headings through the written table of
`spec_to_inspector.bench.mapping`. A row also carries what the anomaly model's
most anomalous region lies on: VisA's masks number their defect types, so the
types under region 1 are read from the model's test run, where a region is
known. That part is a property of the trained model's regions, not of VisA
alone, and the bench checks it against its own inference.

    uv run python -m spec_to_inspector.bench.labels

rebuilds `eval/clause_labels.csv` from the fetched data and the test runs.
A list in a field is comma-separated, as VisA writes its own.
"""

import csv
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, Self

import typer
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from spec_to_inspector.anomaly.ground_truth import defect_types
from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.anomaly.split import SplitError, split_images
from spec_to_inspector.bench.mapping import PARTS, MappingError, expected_headings
from spec_to_inspector.settings import Settings

DEFAULT_LABELS: Final = Path("eval/clause_labels.csv")
LABEL_COLUMNS: Final[tuple[str, ...]] = (
    "part",
    "image_id",
    "visa_image",
    "anno_line",
    "visa_types",
    "defects",
    "expected_headings",
    "region1",
    "region1_types",
    "region1_headings",
)
ANNOTATION_NAME: Final = "image_anno.csv"
_RESULT_NAME: Final = "result.json"
_LIST_COLUMNS: Final = frozenset(
    {"visa_types", "expected_headings", "region1_types", "region1_headings"}
)

RegionTruth = Mapping[str, tuple[str, ...] | None]
"""Per image id, the VisA types under region 1; None for an image with no region."""


class LabelError(ValueError):
    """The labelled set cannot be derived or read as asked; the message says why."""


class Region1(StrEnum):
    """What the anomaly model's most anomalous region lies on, by VisA's mask."""

    NO_REGION = "no region"
    OFF_DEFECT = "off the labelled defect"
    ONE_TYPE = "one type"
    SEVERAL_TYPES = "several types"


def _region1_status(types: tuple[str, ...] | None) -> Region1:
    """Name what region 1 lies on.

    Args:
        types: The VisA types under region 1; None for an image with no region.

    Returns:
        The status in words.
    """
    if types is None:
        return Region1.NO_REGION
    if not types:
        return Region1.OFF_DEFECT
    return Region1.ONE_TYPE if len(types) == 1 else Region1.SEVERAL_TYPES


class ClauseLabel(BaseModel):
    """One anomalous test image and the clause a correct citation names.

    Attributes:
        part: The part, as VisA names its category.
        image_id: The image's id in a run of the test split, such as `bad-000`.
        visa_image: The image's path in VisA's CSVs.
        anno_line: The line of the part's `image_anno.csv` that names it,
            counted from 1 with the header as line 1.
        visa_types: The defect types that line names, in its order.
        defects: `single` for one defect type, `multi` for several.
        expected_headings: The heading that covers each type, in the same
            order, through the mapping table.
        region1: What the anomaly model's most anomalous region lies on.
        region1_types: The VisA types under that region, in order of mask value.
        region1_headings: The headings that cover those types.
    """

    model_config = ConfigDict(frozen=True)

    part: str
    image_id: str
    visa_image: str
    anno_line: int
    visa_types: tuple[str, ...]
    defects: Literal["single", "multi"]
    expected_headings: tuple[str, ...]
    region1: Region1
    region1_types: tuple[str, ...]
    region1_headings: tuple[str, ...]

    @model_validator(mode="after")
    def _derived_columns_agree(self) -> Self:
        """Refuse a row whose derived columns are not what its types derive.

        Returns:
            The label unchanged.

        Raises:
            ValueError: If the row names no type, or a derived column was
                changed by hand.
        """
        if not self.visa_types:
            msg = "the row names no defect type"
            raise ValueError(msg)
        if self.defects != ("single" if len(self.visa_types) == 1 else "multi"):
            msg = f"`defects` is {self.defects} for {len(self.visa_types)} defect type(s)"
            raise ValueError(msg)
        for column, types, written in (
            ("expected_headings", self.visa_types, self.expected_headings),
            ("region1_headings", self.region1_types, self.region1_headings),
        ):
            mapped = expected_headings(self.part, types)
            if written != mapped:
                msg = f"`{column}` is {written}, but the mapping table gives {mapped}"
                raise ValueError(msg)
        if not set(self.region1_types) <= set(self.visa_types):
            msg = (
                f"region 1 lies on {self.region1_types}, which the annotation's "
                f"{self.visa_types} does not hold"
            )
            raise ValueError(msg)
        if self.region1 is not Region1.NO_REGION and self.region1 is not _region1_status(
            self.region1_types
        ):
            msg = f"`region1` is {self.region1.value!r} for {len(self.region1_types)} type(s)"
            raise ValueError(msg)
        if self.region1 is Region1.NO_REGION and self.region1_types:
            msg = "`region1` says no region, yet types are given under it"
            raise ValueError(msg)
        return self

    @property
    def single(self) -> bool:
        """Whether the image carries one defect type, so that its clause is unambiguous."""
        return self.defects == "single"


def region1_types(result: ImageResult) -> tuple[str, ...] | None:
    """Read the VisA defect types under an image's most anomalous region.

    Args:
        result: The anomaly model's sidecar for the image.

    Returns:
        The types in order of mask value, empty for a region on no labelled
        defect; None for an image with no region at all.
    """
    if not result.regions:
        return None
    return tuple(defect_types(result.category, result.regions[0].ground_truth_values or ()))


def read_region_truth(
    run_directory: Path, image_ids: Iterable[str]
) -> dict[str, tuple[str, ...] | None]:
    """Read region 1's own defect types for some images of a run.

    Args:
        run_directory: A run the anomaly model wrote.
        image_ids: The images wanted.

    Returns:
        Per image id, the types under region 1, or None for no region.

    Raises:
        LabelError: If the run holds no readable sidecar for an image.
    """
    truth: dict[str, tuple[str, ...] | None] = {}
    for image_id in image_ids:
        path = run_directory / image_id / _RESULT_NAME
        try:
            result = ImageResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            msg = f"the run {run_directory} holds no readable result for {image_id}: {error}"
            raise LabelError(msg) from error
        truth[image_id] = region1_types(result)
    return truth


def _split(text: str) -> tuple[str, ...]:
    """Read a comma-separated field, as VisA writes several defect types.

    Args:
        text: The field.

    Returns:
        Its entries, stripped, without repeats, in the order written.
    """
    return tuple(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))


def _annotations(visa_dir: Path, part: str) -> dict[str, tuple[int, str]]:
    """Read a part's annotation file, keeping each line's number.

    Args:
        visa_dir: The dataset directory `data fetch` wrote.
        part: The part.

    Returns:
        Per image path, the line that names it and its label.

    Raises:
        LabelError: If the file is missing or lacks its columns.
    """
    path = visa_dir / part / ANNOTATION_NAME
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header: list[str] = next(reader, None) or []
            if header[:2] != ["image", "label"]:
                msg = f"{path} does not begin with the columns image, label"
                raise LabelError(msg)
            return {row[0]: (reader.line_num, row[1]) for row in reader if len(row) > 1}
    except OSError as error:
        msg = f"{path} cannot be read: run `spec-to-inspector data fetch` first ({error})"
        raise LabelError(msg) from error


def derive_labels(visa_dir: Path, part: str, region_truth: RegionTruth) -> list[ClauseLabel]:
    """Derive the label of every anomalous test image of a part.

    Args:
        visa_dir: The dataset directory `data fetch` wrote.
        part: The part.
        region_truth: Per image id, the VisA types under the anomaly model's
            region 1; None for an image with no region. Every image must have
            an entry.

    Returns:
        The labels, in the order of VisA's split file.

    Raises:
        LabelError: If the data cannot be read, an image has no annotation
            line or no region truth, a type has no row in the mapping table,
            or a region lies on a type its annotation line does not name.
    """
    try:
        images = [image for image in split_images(visa_dir, part, "test") if image.label == "bad"]
    except SplitError as error:
        raise LabelError(str(error)) from error
    annotations = _annotations(visa_dir, part)
    labels: list[ClauseLabel] = []
    for image in images:
        image_id = f"{image.label}-{image.path.stem}"
        if image.visa_image not in annotations:
            msg = f"{part}/{ANNOTATION_NAME} has no line for {image.visa_image}"
            raise LabelError(msg)
        if image_id not in region_truth:
            msg = f"no region truth was given for {part} {image_id}"
            raise LabelError(msg)
        line, label = annotations[image.visa_image]
        types = _split(label)
        under = region_truth[image_id]
        try:
            labels.append(
                ClauseLabel(
                    part=part,
                    image_id=image_id,
                    visa_image=image.visa_image,
                    anno_line=line,
                    visa_types=types,
                    defects="single" if len(types) == 1 else "multi",
                    expected_headings=expected_headings(part, types),
                    region1=_region1_status(under),
                    region1_types=under or (),
                    region1_headings=expected_headings(part, under or ()),
                )
            )
        except (MappingError, ValidationError) as error:
            msg = f"{part} {image_id} ({image.visa_image}, line {line}): {error}"
            raise LabelError(msg) from error
    return labels


def write_labels(path: Path, labels: Sequence[ClauseLabel]) -> None:
    """Write the labelled set as CSV.

    Args:
        path: The file, created with its directory if absent.
        labels: The labels, in the order to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(LABEL_COLUMNS)
        for label in labels:
            fields = label.model_dump(mode="json")
            writer.writerow(
                ",".join(fields[column]) if column in _LIST_COLUMNS else fields[column]
                for column in LABEL_COLUMNS
            )


def read_labels(path: Path) -> list[ClauseLabel]:
    """Read the labelled set, checking every row against the mapping table.

    Args:
        path: The file `write_labels` wrote.

    Returns:
        The labels, in the file's order.

    Raises:
        LabelError: If the file cannot be read, lacks its columns, names an
            image twice, or holds a row whose derived columns are not what its
            defect types derive.
    """
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LABEL_COLUMNS:
                msg = f"{path} does not have the columns {', '.join(LABEL_COLUMNS)}"
                raise LabelError(msg)
            rows = [(reader.line_num, row) for row in reader]
    except OSError as error:
        msg = f"the labelled set {path} cannot be read: {error}"
        raise LabelError(msg) from error
    labels: list[ClauseLabel] = []
    seen: set[tuple[str, str]] = set()
    for line, row in rows:
        fields: dict[str, object] = {
            column: _split(value) if column in _LIST_COLUMNS else value
            for column, value in row.items()
        }
        try:
            label = ClauseLabel.model_validate(fields)
        except (MappingError, ValidationError) as error:
            msg = f"{path}, line {line}: {error}"
            raise LabelError(msg) from error
        if (label.part, label.image_id) in seen:
            msg = f"{path}, line {line}: {label.part} {label.image_id} is named twice"
            raise LabelError(msg)
        seen.add((label.part, label.image_id))
        labels.append(label)
    return labels


def main(
    out: Annotated[
        Path, typer.Option("--out", help="Where the labelled set is written.")
    ] = DEFAULT_LABELS,
    run_name: Annotated[
        str,
        typer.Option(
            "--run",
            help="The name of each part's run that region 1's own defect types are read from, "
            "<runs-dir>/<part>/<name>; the anomaly model's test run by default.",
        ),
    ] = "test",
) -> None:
    """Rebuild the labelled set from the fetched VisA data and the anomaly model's test runs."""
    settings = Settings()
    labels: list[ClauseLabel] = []
    try:
        for part in PARTS:
            run = settings.runs_dir / part / run_name
            images = [
                f"{image.label}-{image.path.stem}"
                for image in split_images(settings.visa_dir, part, "test")
                if image.label == "bad"
            ]
            labels.extend(derive_labels(settings.visa_dir, part, read_region_truth(run, images)))
    except (LabelError, SplitError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    write_labels(out, labels)
    single = sum(label.single for label in labels)
    typer.echo(
        f"{len(labels)} anomalous test images of {' and '.join(PARTS)}: {single} single-defect, "
        f"{len(labels) - single} multi-defect.\nLabelled set: {out}"
    )


if __name__ == "__main__":
    typer.run(main)
