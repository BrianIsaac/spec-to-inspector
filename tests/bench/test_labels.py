"""Tests for deriving the labelled set from VisA's annotation and the mapping table."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from spec_to_inspector.anomaly.records import Box, ImageResult, Region
from spec_to_inspector.bench.labels import (
    LABEL_COLUMNS,
    ClauseLabel,
    LabelError,
    Region1,
    derive_labels,
    read_labels,
    read_region_truth,
    region1_types,
    write_labels,
)
from spec_to_inspector.bench.mapping import PARTS, expected_headings
from spec_to_inspector.settings import Settings
from tests.datasets.visa_fakes import fake_files, write_tree

ROOT = Path(__file__).parents[2]
TRACKED = ROOT / "eval" / "clause_labels.csv"


def _result(image_id: str, values: list[list[int]] | None, *, part: str = "pcb4") -> ImageResult:
    """Build a sidecar whose regions lie on the given ground-truth mask values.

    Args:
        image_id: The image's id in the run.
        values: Per region, in rank order, the mask values under it; None for
            an image the anomaly model did not flag.
        part: The part.

    Returns:
        The sidecar.
    """
    regions = [
        Region(
            index=rank,
            bbox=Box(x=0, y=0, width=4, height=4),
            area_px=16,
            centroid=(2.0, 2.0),
            peak_score=40.0,
            peak_xy=(2, 2),
            mean_score=35.0,
            on_ground_truth=bool(under),
            ground_truth_values=under,
        )
        for rank, under in enumerate(values or [], start=1)
    ]
    return ImageResult(
        category=part,
        image_id=image_id,
        image=f"{image_id}.JPG",
        visa_image=None,
        width=64,
        height=48,
        label="bad",
        ground_truth_mask=None,
        score=40.0 if regions else 10.0,
        image_threshold=30.0,
        score_normalised=0.6,
        predicted_anomalous=bool(regions),
        pixel_threshold=30.0,
        region_threshold=30.0,
        region_threshold_source="image",
        map_width=256,
        map_height=256,
        map_max=40.0,
        anomaly_map="anomaly_map.npy",
        mask="mask.png",
        mask_pixels=16 * len(regions),
        regions_image="regions.png",
        regions=regions,
    )


@pytest.fixture
def visa(tmp_path: Path) -> Path:
    """Write the synthetic VisA: three anomalous images on each of pcb1 and pcb4.

    Returns:
        The dataset directory.
    """
    root = tmp_path / "visa"
    write_tree(root, fake_files())
    return root


def test_region_one_takes_the_types_under_it_from_the_mask_values() -> None:
    """Region 1's own truth is VisA's types under it; an unflagged image has none to give."""
    assert region1_types(_result("bad-000", [[1, 7], [2]])) == ("burnt", "dirt")
    assert region1_types(_result("bad-001", [[]])) == ()
    assert region1_types(_result("bad-002", None)) is None


def test_a_label_is_the_annotation_line_mapped_through_the_table(visa: Path) -> None:
    """Each anomalous test image gets its line, its types, its headings and region 1's truth."""
    truth = {"bad-000": ("dirt",), "bad-001": (), "bad-002": None}
    labels = derive_labels(visa, "pcb4", truth)

    assert [label.image_id for label in labels] == ["bad-000", "bad-001", "bad-002"]
    first, second, third = labels
    assert first.visa_image == "pcb4/Data/Images/Anomaly/000.JPG"
    assert first.anno_line == 5
    assert first.visa_types == ("wrong place", "dirt")
    assert first.defects == "multi"
    assert first.expected_headings == ("5.4", "5.1")
    assert (first.region1, first.region1_types, first.region1_headings) == (
        Region1.ONE_TYPE,
        ("dirt",),
        ("5.1",),
    )
    assert (second.defects, second.expected_headings) == ("single", ("5.1",))
    assert (second.region1, second.region1_types) == (Region1.OFF_DEFECT, ())
    assert (third.visa_types, third.region1) == (("burnt",), Region1.NO_REGION)


def test_a_region_on_several_types_keeps_them_all(visa: Path) -> None:
    """A region that straddles two labelled defects is not given one of them."""
    truth = {"bad-000": ("bent",), "bad-001": ("melt", "scratch"), "bad-002": ("missing",)}
    second = derive_labels(visa, "pcb1", truth)[1]
    assert (second.region1, second.region1_headings) == (Region1.SEVERAL_TYPES, ("4.1", "4.2"))


def test_an_image_the_run_does_not_hold_is_an_error(visa: Path) -> None:
    """Region truth for some images only would leave the others silently unflagged."""
    with pytest.raises(LabelError, match="bad-002"):
        derive_labels(visa, "pcb4", {"bad-000": None, "bad-001": None})


def test_a_region_on_a_type_the_annotation_does_not_name_is_an_error(visa: Path) -> None:
    """The mask and the annotation line must tell one story."""
    truth = {"bad-000": ("burnt",), "bad-001": None, "bad-002": None}
    with pytest.raises(LabelError, match="burnt"):
        derive_labels(visa, "pcb4", truth)


def test_region_truth_is_read_from_a_runs_sidecars(tmp_path: Path) -> None:
    """The anomaly model's run is read, never written."""
    for image_id, values in (("bad-000", [[7]]), ("bad-001", None)):
        directory = tmp_path / image_id
        directory.mkdir()
        (directory / "result.json").write_text(
            _result(image_id, values).model_dump_json(), encoding="utf-8"
        )
    assert read_region_truth(tmp_path, ["bad-000", "bad-001"]) == {
        "bad-000": ("dirt",),
        "bad-001": None,
    }
    with pytest.raises(LabelError, match="bad-009"):
        read_region_truth(tmp_path, ["bad-009"])


def test_the_file_round_trips_and_lists_are_comma_separated_as_visa_writes_them(
    visa: Path, tmp_path: Path
) -> None:
    """What is written is what is read; a list is one quoted field."""
    labels = derive_labels(visa, "pcb4", {"bad-000": ("dirt",), "bad-001": (), "bad-002": None})
    path = tmp_path / "eval" / "clause_labels.csv"
    write_labels(path, labels)

    assert read_labels(path) == labels
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == LABEL_COLUMNS
    assert rows[1][4:7] == ["wrong place,dirt", "multi", "5.4,5.1"]


def test_a_file_whose_headings_are_not_the_tables_is_refused(visa: Path, tmp_path: Path) -> None:
    """An edited expected heading is caught on reading, not at scoring."""
    path = tmp_path / "clause_labels.csv"
    write_labels(
        path, derive_labels(visa, "pcb4", dict.fromkeys(["bad-000", "bad-001", "bad-002"]))
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("5.4,5.1", "5.4,5.2"), encoding="utf-8"
    )
    with pytest.raises(LabelError, match="line 2"):
        read_labels(path)


def test_the_tracked_set_is_200_images_135_of_them_single_defect() -> None:
    """The counts of the plan's 3.4: pcb1 91 and 9, pcb4 44 and 56; no dirt image stands alone."""
    labels = read_labels(TRACKED)
    counted = Counter((label.part, label.defects) for label in labels)
    assert counted == {
        ("pcb1", "single"): 91,
        ("pcb1", "multi"): 9,
        ("pcb4", "single"): 44,
        ("pcb4", "multi"): 56,
    }
    assert len({(label.part, label.image_id) for label in labels}) == 200
    assert all(label.part in PARTS for label in labels)
    single = Counter((label.part, label.visa_types[0]) for label in labels if label.single)
    assert ("pcb4", "dirt") not in single
    assert single["pcb1", "melt"] == 46


def test_every_tracked_row_is_its_types_mapped_through_the_table() -> None:
    """The expected headings are derived, row by row, and never typed in."""
    for label in read_labels(TRACKED):
        assert label.expected_headings == expected_headings(label.part, label.visa_types)
        assert set(label.region1_types) <= set(label.visa_types)


@pytest.mark.data
def test_every_tracked_row_traces_to_its_annotation_line() -> None:
    """Line `anno_line` of the part's `image_anno.csv` names the image and its types."""
    visa_dir = Settings().visa_dir
    lines = {
        part: (visa_dir / part / "image_anno.csv").read_text(encoding="utf-8").splitlines()
        for part in PARTS
    }
    labels = read_labels(TRACKED)
    for label in labels:
        row = next(csv.reader([lines[label.part][label.anno_line - 1]]))
        assert row[0] == label.visa_image
        assert row[1] == ",".join(label.visa_types)
    assert len(labels) == 200


@pytest.mark.data
def test_the_tracked_set_is_what_the_data_and_the_test_runs_derive() -> None:
    """Rebuilding from the fetched data and the anomaly model's test runs changes nothing."""
    settings = Settings()
    rebuilt: list[ClauseLabel] = []
    for part in PARTS:
        run = settings.runs_dir / part / "test"
        if not run.is_dir():
            pytest.skip(f"the anomaly model's test run {run} is not on this machine")
        ids = [f"bad-{number:03d}" for number in range(100)]
        rebuilt.extend(derive_labels(settings.visa_dir, part, read_region_truth(run, ids)))
    assert rebuilt == read_labels(TRACKED)
