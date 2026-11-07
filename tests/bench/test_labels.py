"""Tests for deriving the labelled set from VisA's annotation and the mapping table."""

import csv
import hashlib
from collections import Counter
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from spec_to_inspector.anomaly.records import Box, ImageResult, Region
from spec_to_inspector.bench import labels as labels_module
from spec_to_inspector.bench.labels import (
    DEFAULT_RUN,
    LABEL_COLUMNS,
    REGION_COLUMNS,
    ClauseLabel,
    LabelError,
    Region1,
    RegionColumnsChange,
    derive_labels,
    main,
    read_labels,
    read_region_truth,
    region1_types,
    region_changes,
    write_labels,
)
from spec_to_inspector.bench.mapping import PARTS, expected_headings
from spec_to_inspector.settings import Settings
from tests.datasets.visa_fakes import fake_files, write_tree

ROOT = Path(__file__).parents[2]
TRACKED = ROOT / "eval" / "clause_labels.csv"


def _labels_app() -> typer.Typer:
    """Give the labels' command as an app a runner can invoke.

    Returns:
        The app.
    """
    app = typer.Typer()
    app.command()(main)
    return app


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
def test_the_tracked_labels_are_what_the_data_derive_on_any_machine() -> None:
    """The columns that come from VisA through the mapping table, which no model decides."""
    settings = Settings()
    no_regions = dict.fromkeys(f"bad-{number:03d}" for number in range(100))
    derived = [row for part in PARTS for row in derive_labels(settings.visa_dir, part, no_regions)]
    tracked = read_labels(TRACKED)

    kept = [column for column in LABEL_COLUMNS if column not in REGION_COLUMNS]
    assert [[getattr(row, column) for column in kept] for row in derived] == [
        [getattr(row, column) for column in kept] for row in tracked
    ]


@pytest.mark.data
def test_the_tracked_columns_are_what_the_benchs_runs_on_the_named_checkpoints_derive() -> None:
    """On the machine, from a whole run of each part as the bench batches it, nothing changes."""
    settings = Settings()
    if settings.stage != "II":
        pytest.skip("the region columns are of the machine's checkpoints, and this is not it")
    rebuilt: list[ClauseLabel] = []
    for part in PARTS:
        run = settings.runs_dir / part / DEFAULT_RUN
        if not run.is_dir():
            pytest.skip(f"the bench's whole run {run} is not on this machine")
        ids = [f"bad-{number:03d}" for number in range(100)]
        rebuilt.extend(derive_labels(settings.visa_dir, part, read_region_truth(run, ids)))
    assert rebuilt == read_labels(TRACKED)


def _rows(visa: Path, under: dict[str, tuple[str, ...] | None]) -> list[ClauseLabel]:
    return derive_labels(
        visa, "pcb4", {"bad-000": ("dirt",), "bad-001": (), "bad-002": None} | under
    )


def test_the_changed_rows_are_given_board_by_board_old_and_new(visa: Path) -> None:
    """The addition's table: a board gaining a region, one losing it; the others are not listed."""
    old = _rows(visa, {})
    new = _rows(visa, {"bad-000": None, "bad-002": ("burnt",)})

    changes = region_changes(old, new)

    assert [(c.part, c.image_id) for c in changes] == [("pcb4", "bad-000"), ("pcb4", "bad-002")]
    first = changes[0]
    assert (first.old_region1, first.old_types, first.old_headings) == (
        Region1.ONE_TYPE,
        ("dirt",),
        ("5.1",),
    )
    assert (first.new_region1, first.new_types, first.new_headings) == (Region1.NO_REGION, (), ())
    assert changes[1].old_region1 is Region1.NO_REGION
    assert changes[1].new_types == ("burnt",)


def test_no_change_is_an_empty_table(visa: Path) -> None:
    """The columns of the same model's run: nothing to list."""
    assert region_changes(_rows(visa, {}), _rows(visa, {})) == []


def test_a_change_to_the_labels_themselves_is_refused(visa: Path) -> None:
    """They come from VisA through the mapping, not from a model: the addition says they stay."""
    old = _rows(visa, {})
    moved = old[0].model_copy(update={"anno_line": old[0].anno_line + 1})

    with pytest.raises(LabelError, match="anno_line"):
        region_changes(old, [moved, *old[1:]])


def test_a_board_gained_or_lost_is_refused(visa: Path) -> None:
    """The set is all 200, no image left out for any reason."""
    old = _rows(visa, {})

    with pytest.raises(LabelError, match="bad-002"):
        region_changes(old, old[:2])
    with pytest.raises(LabelError, match="bad-002"):
        region_changes(old[:2], old)


def _command(tmp_path: Path, visa: Path, under: dict[str, str | None]) -> Path:
    """Lay out runs for the labels' command: one part, with a sidecar per board.

    Args:
        tmp_path: The working root.
        visa: The fetched data.
        under: Per board, the mask value's type under region 1; None for no region.

    Returns:
        The runs directory.
    """
    runs = tmp_path / "runs"
    values = {"burnt": 1, "dirt": 7}
    for image_id, kind in under.items():
        result = _result(image_id, None if kind is None else [[values[kind]]])
        path = runs / "pcb4" / "bench" / image_id / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(), encoding="utf-8")
    return runs


def test_the_command_writes_the_columns_and_the_table_and_keeps_the_labels(
    visa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same code as ever, from the bench's own run, with the addition's table beside it."""
    out = tmp_path / "clause_labels.csv"
    write_labels(out, _rows(visa, {}))
    before = out.read_bytes()
    runs = _command(tmp_path, visa, {"bad-000": "dirt", "bad-001": None, "bad-002": "burnt"})
    changes_path = tmp_path / "region-columns" / "changes.json"
    monkeypatch.setattr(labels_module, "PARTS", ("pcb4",))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(visa.parent))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(runs))

    result = CliRunner().invoke(_labels_app(), ["--out", str(out), "--changes", str(changes_path)])

    assert result.exit_code == 0, result.output
    written = RegionColumnsChange.model_validate_json(changes_path.read_text(encoding="utf-8"))
    assert written.run == "bench"
    assert written.rows == 3
    assert [change.image_id for change in written.changes] == ["bad-001", "bad-002"]
    assert written.old_sha256 == hashlib.sha256(before).hexdigest()
    assert written.new_sha256 == hashlib.sha256(out.read_bytes()).hexdigest()
    assert written.new_sha256 != written.old_sha256
    assert "pcb4 bad-001" in result.output
    assert "off the labelled defect" in result.output
    kept = read_labels(out)
    assert [row.visa_types for row in kept] == [row.visa_types for row in _rows(visa, {})]
    assert [row.expected_headings for row in kept] == [
        row.expected_headings for row in _rows(visa, {})
    ]


def test_the_command_refuses_a_part_whose_run_is_not_whole(
    visa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run cut down by --limit has no sidecar for the rest, and the file stays as it was."""
    out = tmp_path / "clause_labels.csv"
    write_labels(out, _rows(visa, {}))
    before = out.read_bytes()
    runs = _command(tmp_path, visa, {"bad-000": "dirt"})
    monkeypatch.setattr(labels_module, "PARTS", ("pcb4",))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(visa.parent))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(runs))

    result = CliRunner().invoke(_labels_app(), ["--out", str(out)])

    assert result.exit_code == 1
    assert "bad-001" in result.output
    assert out.read_bytes() == before


def test_the_tracked_columns_are_the_regenerated_ones_on_record() -> None:
    """The addition's record: the file's digest is the one the regeneration wrote."""
    written = RegionColumnsChange.model_validate_json(
        (ROOT / "results" / "stage2" / "region-columns" / "changes.json").read_text("utf-8")
    )

    assert hashlib.sha256(TRACKED.read_bytes()).hexdigest() == written.new_sha256
    assert written.rows == 200
