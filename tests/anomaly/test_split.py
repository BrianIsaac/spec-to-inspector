"""Tests for the VisA one-class split in Anomalib's `visa_pytorch` layout."""

import csv
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest
from anomalib.data import Visa
from anomalib.data.datasets.image.visa import VisaDataset
from anomalib.data.utils import Split

from spec_to_inspector.anomaly.split import SPLIT_ROOT, SplitError, write_split
from spec_to_inspector.datasets.visa import SPLIT_CSV, SPLIT_DIR, tree_digest, verify
from tests.anomaly.fakes import categories, write_visa
from tests.datasets.visa_fakes import EXPECTED


@pytest.fixture
def visa(tmp_path: Path) -> Path:
    """A synthetic VisA holding only the PCB categories, as `data fetch` leaves it.

    Returns:
        The dataset directory.
    """
    root = tmp_path / "visa"
    write_visa(root)
    return root


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_the_layout_is_anomalibs_and_the_counts_are_the_csvs(visa: Path) -> None:
    """Each category gets train/good, test/good, test/bad and ground_truth/bad, by the CSV."""
    result = write_split(visa, categories())

    base = visa / SPLIT_ROOT / "pcb1"
    assert sorted(p.name for p in (base / "train" / "good").iterdir()) == [
        "0000.JPG",
        "0001.JPG",
        "0002.JPG",
    ]
    assert sorted(p.name for p in (base / "test" / "good").iterdir()) == ["0003.JPG", "0004.JPG"]
    assert sorted(p.name for p in (base / "test" / "bad").iterdir()) == [
        "000.JPG",
        "001.JPG",
        "002.JPG",
    ]
    assert sorted(p.name for p in (base / "ground_truth" / "bad").iterdir()) == [
        "000.png",
        "001.png",
        "002.png",
    ]
    assert result["pcb1"].path == base
    assert (result["pcb1"].train_good, result["pcb1"].test_good) == (3, 2)
    assert (result["pcb1"].test_bad, result["pcb1"].masks) == (3, 3)
    assert (result["pcb4"].train_good, result["pcb4"].test_good, result["pcb4"].test_bad) == (
        2,
        1,
        3,
    )
    assert result["pcb1"].written
    assert result["pcb4"].written


def test_images_are_hardlinks_of_the_source(visa: Path) -> None:
    """An image in the split is the source's own inode, so the split costs no disk."""
    result = write_split(visa, categories())

    source = visa / "pcb1/Data/Images/Normal/0000.JPG"
    linked = visa / SPLIT_ROOT / "pcb1/train/good/0000.JPG"
    assert linked.samefile(source)
    assert source.stat().st_nlink == 2
    assert result["pcb1"].linked == 8
    assert result["pcb1"].copied == 0


def test_masks_are_binarised_to_0_and_255(visa: Path) -> None:
    """A mask's defect indices become 255 and its background stays 0."""
    write_split(visa, categories())

    source = cv2.imread(str(visa / "pcb4/Data/Masks/Anomaly/001.png"), cv2.IMREAD_UNCHANGED)
    written = cv2.imread(
        str(visa / SPLIT_ROOT / "pcb4/ground_truth/bad/001.png"), cv2.IMREAD_UNCHANGED
    )
    assert source is not None
    assert written is not None
    assert set(np.unique(source).tolist()) == {0, 1, 2}
    assert set(np.unique(written).tolist()) == {0, 255}
    assert np.array_equal(written[..., 0] == 255, source != 0)


def test_the_split_equals_anomalibs_own_on_a_whole_tree(tmp_path: Path) -> None:
    """On a tree that holds every category its CSV names, Anomalib writes the same files."""
    ours, theirs = tmp_path / "ours", tmp_path / "theirs"
    write_visa(ours, kept_only=False)
    shutil.copytree(ours, theirs)

    write_split(ours, categories())
    Visa(root=theirs, category="pcb1").apply_cls1_split()

    for category in categories():
        expected = _tree(theirs / SPLIT_ROOT / category)
        assert expected
        assert _tree(ours / SPLIT_ROOT / category) == expected


def test_only_the_asked_categories_are_written(visa: Path) -> None:
    """Rows of categories that are not asked for, or not on disk, are passed over."""
    result = write_split(visa, ["pcb4"])

    assert list(result) == ["pcb4"]
    assert sorted(p.name for p in (visa / SPLIT_ROOT).iterdir()) == ["pcb4"]


def test_anomalib_reads_the_split_and_pairs_the_masks(visa: Path) -> None:
    """Anomalib's VisA dataset finds the training images and each anomalous image's mask."""
    write_split(visa, categories())

    train = VisaDataset(root=visa / SPLIT_ROOT, category="pcb1", split=Split.TRAIN)
    test = VisaDataset(root=visa / SPLIT_ROOT, category="pcb1", split=Split.TEST)

    assert len(train) == 3
    assert len(test) == 5
    anomalous = test.samples[test.samples.label_index == 1]
    assert [Path(p).stem for p in anomalous.image_path] == ["000", "001", "002"]
    assert [Path(p).stem for p in anomalous.mask_path] == ["000", "001", "002"]


def test_anomalibs_prepare_data_accepts_the_split(visa: Path) -> None:
    """With the split in place, Anomalib's own preparation finds it and does nothing."""
    write_split(visa, categories())
    before = _tree(visa)

    Visa(root=visa, category="pcb4").prepare_data()

    assert _tree(visa) == before


def test_a_second_write_changes_nothing(visa: Path) -> None:
    """The split is idempotent: a complete category is found and left alone."""
    write_split(visa, categories())
    mask = visa / SPLIT_ROOT / "pcb1/ground_truth/bad/000.png"
    before = _tree(visa / SPLIT_ROOT)
    stamp = mask.stat().st_mtime_ns

    result = write_split(visa, categories())

    assert not result["pcb1"].written
    assert not result["pcb4"].written
    assert result["pcb1"].train_good == 3
    assert _tree(visa / SPLIT_ROOT) == before
    assert mask.stat().st_mtime_ns == stamp


@pytest.mark.parametrize("damage", ["missing", "stale", "truncated", "replaced"])
def test_a_damaged_category_is_rebuilt(visa: Path, damage: str) -> None:
    """A category with a missing, extra, empty or foreign file is written afresh."""
    write_split(visa, categories())
    base = visa / SPLIT_ROOT / "pcb1"
    whole = _tree(base)
    if damage == "missing":
        (base / "test/bad/001.JPG").unlink()
    elif damage == "stale":
        (base / "train/good/9999.JPG").write_bytes(b"left over")
    elif damage == "truncated":
        (base / "ground_truth/bad/002.png").write_bytes(b"")
    else:
        (base / "train/good/0001.JPG").unlink()
        (base / "train/good/0001.JPG").write_bytes(b"not the source")

    result = write_split(visa, categories())

    assert result["pcb1"].written
    assert not result["pcb4"].written
    assert _tree(base) == whole
    assert not list((visa / SPLIT_ROOT).glob(".*"))


def test_the_split_leaves_the_fetched_tree_verifiable(visa: Path) -> None:
    """U1's verification and tree digest are the same before and after the split."""
    members = (*categories(), SPLIT_DIR)
    before = tree_digest(visa, members)

    write_split(visa, categories())

    assert verify(visa, EXPECTED) == EXPECTED
    assert tree_digest(visa, members) == before


def test_a_category_the_csv_does_not_name_is_refused(visa: Path) -> None:
    """Asking for a category with no rows is an error, not an empty split."""
    with pytest.raises(SplitError, match="pcb9"):
        write_split(visa, ["pcb9"])

    assert not (visa / SPLIT_ROOT / "pcb9").exists()


def test_a_missing_source_image_is_named(visa: Path) -> None:
    """A row whose image is not on disk stops the split and names the file."""
    (visa / "pcb1/Data/Images/Normal/0002.JPG").unlink()

    with pytest.raises(SplitError, match=r"pcb1/Data/Images/Normal/0002\.JPG"):
        write_split(visa, categories())

    assert not (visa / SPLIT_ROOT / "pcb1").exists()
    assert not list((visa / SPLIT_ROOT).glob(".*"))


def test_an_unreadable_mask_is_named(visa: Path) -> None:
    """A mask that does not decode stops the split and names the file."""
    (visa / "pcb4/Data/Masks/Anomaly/000.png").write_bytes(b"not a png")

    with pytest.raises(SplitError, match=r"pcb4/Data/Masks/Anomaly/000\.png"):
        write_split(visa, categories())

    assert not (visa / SPLIT_ROOT / "pcb4").exists()


def _rewrite_rows(visa: Path, old: str, new: str) -> None:
    path = visa / SPLIT_DIR / SPLIT_CSV
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [[cell.replace(old, new) for cell in row] for row in csv.reader(handle)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def test_a_row_that_leaves_the_dataset_is_refused(visa: Path, tmp_path: Path) -> None:
    """A CSV path that climbs out of the dataset directory is never followed."""
    (tmp_path / "outside.JPG").write_bytes(b"outside")
    _rewrite_rows(visa, "pcb1/Data/Images/Normal/0000.JPG", "../outside.JPG")

    with pytest.raises(SplitError, match="outside the dataset"):
        write_split(visa, categories())


def test_an_anomalous_row_without_a_mask_is_refused(visa: Path) -> None:
    """An anomalous test image must name its mask."""
    _rewrite_rows(visa, "pcb1/Data/Masks/Anomaly/001.png", "")

    with pytest.raises(SplitError, match="no mask"):
        write_split(visa, categories())


def test_a_missing_split_csv_is_named(visa: Path) -> None:
    """Without `split_csv/1cls.csv` the split says what to run."""
    (visa / SPLIT_DIR / SPLIT_CSV).unlink()

    with pytest.raises(SplitError, match="data fetch"):
        write_split(visa, categories())
