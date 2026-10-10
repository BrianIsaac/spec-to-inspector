"""VisA's one-class split for the PCB categories, in Anomalib's `visa_pytorch` layout.

Anomalib's own `Visa.apply_cls1_split()` walks every row of `1cls.csv`, all
twelve categories, and fails on a tree that holds only the four PCB ones. This
module writes the same split for the categories asked for and nothing else:

    <visa_dir>/visa_pytorch/<category>/train/good/<name>.JPG
    <visa_dir>/visa_pytorch/<category>/test/good/<name>.JPG
    <visa_dir>/visa_pytorch/<category>/test/bad/<name>.JPG
    <visa_dir>/visa_pytorch/<category>/ground_truth/bad/<name>.png

Images are hardlinks of the fetched files, so the split costs no disk; masks
are binarised to 0 and 255 exactly as Anomalib does (read by OpenCV in colour,
every non-zero value set to 255, written as PNG). A category is built in a
partial directory and renamed into place, so `visa_pytorch/<category>/` either
holds the whole split or does not exist; a second call finds it whole and
leaves it alone.
"""

import csv
import filecmp
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import cv2
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.datasets.visa import NORMAL_LABEL, PUBLISHED_COUNTS, SPLIT_CSV, SPLIT_DIR

SPLIT_ROOT: Final = "visa_pytorch"
PCB_CATEGORIES: Final[tuple[str, ...]] = tuple(PUBLISHED_COUNTS)
ANOMALY_LABEL: Final = "anomaly"

_COLUMNS: Final[tuple[str, ...]] = ("object", "split", "label", "image", "mask")
_SPLITS: Final = frozenset({"train", "test"})
_LEAVES: Final[tuple[str, ...]] = ("train/good", "test/good", "test/bad", "ground_truth/bad")


class SplitError(RuntimeError):
    """The split could not be written from the fetched tree."""


class CategorySplit(BaseModel):
    """One category's split on disk.

    Attributes:
        category: The category's name, such as "pcb4".
        path: The category's directory under `visa_pytorch/`.
        train_good: Normal training images.
        test_good: Normal test images.
        test_bad: Anomalous test images.
        masks: Binarised ground-truth masks, one per anomalous test image.
        linked: Images that share the fetched file's inode.
        copied: Images that had to be copied because a hardlink was refused.
        written: Whether this call wrote the category; false when it was found whole.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    path: Path
    train_good: int
    test_good: int
    test_bad: int
    masks: int
    linked: int
    copied: int
    written: bool


@dataclass(frozen=True)
class _Entry:
    """One file of a category's split: where it comes from and where it goes."""

    source: Path
    target: PurePosixPath
    is_mask: bool


def _resolve(visa_dir: Path, name: str, row: int) -> Path:
    """Resolve a path the CSV names, refusing one that leaves the dataset or is absent."""
    root = visa_dir.resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        msg = f"{SPLIT_CSV} row {row}: {name} resolves outside the dataset directory {visa_dir}"
        raise SplitError(msg)
    if not path.is_file():
        msg = f"{SPLIT_CSV} row {row}: {name} is named but missing under {visa_dir}"
        raise SplitError(msg)
    return path


def _read_rows(visa_dir: Path) -> list[dict[str, str]]:
    """Read `split_csv/1cls.csv`, checking its columns."""
    path = visa_dir / SPLIT_DIR / SPLIT_CSV
    if not path.is_file():
        msg = f"{path} is missing: run `spec-to-inspector data fetch` first"
        raise SplitError(msg)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            msg = f"{path} lacks the columns {sorted(missing)}"
            raise SplitError(msg)
        return list(reader)


def _plan(visa_dir: Path, categories: Sequence[str]) -> dict[str, list[_Entry]]:
    """Lay out every file of the asked categories' splits, checking each row.

    Args:
        visa_dir: The dataset directory.
        categories: The categories to plan.

    Returns:
        The entries per category, in the order asked.

    Raises:
        SplitError: If a category has no rows, or a row is malformed, leaves the
            dataset, names a missing file, or collides with another row.
    """
    plan: dict[str, list[_Entry]] = {category: [] for category in categories}
    seen: set[tuple[str, PurePosixPath]] = set()
    for number, row in enumerate(_read_rows(visa_dir), start=2):
        category, split, label = row["object"], row["split"], row["label"]
        if category not in plan:
            continue
        if split not in _SPLITS or label not in {NORMAL_LABEL, ANOMALY_LABEL}:
            msg = f"{SPLIT_CSV} row {number}: unexpected split {split!r} or label {label!r}"
            raise SplitError(msg)
        folder = "good" if label == NORMAL_LABEL else "bad"
        if (split, folder) == ("train", "bad"):
            msg = f"{SPLIT_CSV} row {number}: an anomalous image in the training split"
            raise SplitError(msg)
        entries = [
            _Entry(
                source=_resolve(visa_dir, row["image"], number),
                target=PurePosixPath(split, folder, PurePosixPath(row["image"]).name),
                is_mask=False,
            )
        ]
        if folder == "bad":
            if not row["mask"]:
                msg = f"{SPLIT_CSV} row {number}: {row['image']} is anomalous but names no mask"
                raise SplitError(msg)
            entries.append(
                _Entry(
                    source=_resolve(visa_dir, row["mask"], number),
                    target=PurePosixPath("ground_truth", folder, PurePosixPath(row["mask"]).name),
                    is_mask=True,
                )
            )
        for entry in entries:
            if (category, entry.target) in seen:
                msg = f"{SPLIT_CSV} row {number}: {category}/{entry.target} is named twice"
                raise SplitError(msg)
            seen.add((category, entry.target))
            plan[category].append(entry)
    empty = [category for category, entries in plan.items() if not entries]
    if empty:
        msg = f"{SPLIT_CSV} names no rows for {', '.join(empty)}"
        raise SplitError(msg)
    return plan


def _is_whole(base: Path, entries: Sequence[_Entry]) -> bool:
    """Tell whether a category's directory holds exactly its split, undamaged."""
    if not base.is_dir():
        return False
    found = {
        PurePosixPath(path.relative_to(base).as_posix())
        for path in base.rglob("*")
        if not path.is_dir()
    }
    if found != {entry.target for entry in entries}:
        return False
    for entry in entries:
        target = base / entry.target
        if target.is_symlink():
            return False
        if entry.is_mask:
            if target.stat().st_size == 0:
                return False
        elif not (
            target.samefile(entry.source) or filecmp.cmp(target, entry.source, shallow=False)
        ):
            return False
    return True


def _write_mask(source: Path, target: Path, visa_dir: Path) -> None:
    """Binarise a mask as Anomalib's `apply_cls1_split` does: non-zero becomes 255."""
    mask = cv2.imread(str(source))
    # OpenCV's stubs promise an array, but an undecodable file yields None.
    if mask is None:  # pyright: ignore[reportUnnecessaryComparison]
        msg = f"{source.relative_to(visa_dir.resolve())} is not a readable mask"
        raise SplitError(msg)
    mask[mask != 0] = 255
    if not cv2.imwrite(str(target), mask):
        msg = f"could not write the mask {target}"
        raise SplitError(msg)


def _link(source: Path, target: Path) -> None:
    """Hardlink an image, or copy it where the filesystem refuses a link."""
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def _build(visa_dir: Path, base: Path, entries: Sequence[_Entry]) -> None:
    """Write a category's split into a partial directory and rename it into place."""
    partial = base.with_name(f".{base.name}.partial")
    if partial.exists():
        shutil.rmtree(partial)
    try:
        for leaf in _LEAVES:
            (partial / leaf).mkdir(parents=True)
        for entry in entries:
            target = partial / entry.target
            if entry.is_mask:
                _write_mask(entry.source, target, visa_dir)
            else:
                _link(entry.source, target)
        if base.exists():
            shutil.rmtree(base)
        partial.rename(base)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise


def _describe(category: str, base: Path, entries: Sequence[_Entry], written: bool) -> CategorySplit:
    """Count a whole category's split."""
    folders = [entry.target.parts[:2] for entry in entries]
    images = [entry for entry in entries if not entry.is_mask]
    linked = sum((base / entry.target).samefile(entry.source) for entry in images)
    return CategorySplit(
        category=category,
        path=base,
        train_good=folders.count(("train", "good")),
        test_good=folders.count(("test", "good")),
        test_bad=folders.count(("test", "bad")),
        masks=folders.count(("ground_truth", "bad")),
        linked=linked,
        copied=len(images) - linked,
        written=written,
    )


def write_split(
    visa_dir: Path, categories: Sequence[str] = PCB_CATEGORIES
) -> Mapping[str, CategorySplit]:
    """Write VisA's one-class split for some categories in Anomalib's layout.

    Rows of `split_csv/1cls.csv` for other categories are passed over, so a
    tree that holds only the PCB categories is enough. Every row of the asked
    categories is checked before anything is written. A category already
    whole is left untouched; a damaged one is written afresh.

    Args:
        visa_dir: The dataset directory `data fetch` wrote, holding `<category>/`
            and `split_csv/`.
        categories: The categories to split.

    Returns:
        Each category's split, in the order asked.

    Raises:
        SplitError: If the CSV is missing or malformed, names no rows for a
            category, or names a file that is absent, undecodable or outside
            the dataset directory.
    """
    plan = _plan(visa_dir, categories)
    result: dict[str, CategorySplit] = {}
    for category, entries in plan.items():
        base = visa_dir / SPLIT_ROOT / category
        written = not _is_whole(base, entries)
        if written:
            base.parent.mkdir(parents=True, exist_ok=True)
            _build(visa_dir, base, entries)
        result[category] = _describe(category, base, entries, written)
    return result
