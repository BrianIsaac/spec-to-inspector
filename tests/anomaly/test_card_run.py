"""Tests for the anomaly figures on a card: the stages, the records and the comparisons."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch
from PIL import Image
from typer.testing import CliRunner

from spec_to_inspector.anomaly import card_run
from spec_to_inspector.anomaly.card_run import (
    OPENVINO_BENCH,
    OPENVINO_RUN,
    CardRun,
    Comparison,
    compare_banks,
    compare_part,
    run_openvino,
    run_pytorch,
    timed_stage,
    warm_up_pytorch,
)
from spec_to_inspector.anomaly.infer import MAP_NAME, InferenceItem, load_run_index
from spec_to_inspector.anomaly.ov_model import OpenVinoModel
from spec_to_inspector.anomaly.records import InferenceBench, RunEntry, RunIndex
from spec_to_inspector.card_memory import GpuReading
from tests.anomaly.records_fakes import run_index, train_record


def _entry(image_id: str, score: float, *, flagged: bool = False, regions: int = 0) -> RunEntry:
    return RunEntry(
        image_id=image_id,
        result=f"{image_id}/result.json",
        label="good",
        score=score,
        predicted_anomalous=flagged,
        regions=regions,
        peak_fallback=False,
        top_region_on_ground_truth=None,
    )


def _run(directory: Path, entries: list[RunEntry]) -> RunIndex:
    index = run_index("pcb1").model_copy(update={"entries": entries, "images": len(entries)})
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(index.model_dump_json(), encoding="utf-8")
    return index


def test_a_stage_is_timed_and_the_card_read_while_it_lasts() -> None:
    """Peaks over the readings, the first reading as what it started from."""
    readings = iter([GpuReading(10, None), GpuReading(30, 7), GpuReading(20, 5)])

    def read() -> GpuReading:
        return next(readings, GpuReading(20, 5))

    result, stage = timed_stage("step", read, lambda: "done")

    assert result == "done"
    assert stage.name == "step"
    assert stage.seconds >= 0
    assert stage.memory.gpu_before_mib == 10
    assert stage.memory.interval_seconds == card_run.SAMPLE_SECONDS


def test_two_runs_are_compared_board_by_board(tmp_path: Path) -> None:
    """Flags and regions are counted, and the worst difference of score comes first."""
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a, [_entry("one", 10.0), _entry("two", 20.0, flagged=True, regions=2), _entry("x", 5.0)])
    _run(
        b,
        [
            _entry("one", 10.5),
            _entry("two", 20.0, flagged=False, regions=1),
            _entry("x", 5.0),
        ],
    )

    compared = compare_part("pcb1", a, b)

    assert compared.boards == 3
    assert (compared.flagged_a, compared.flagged_b) == (1, 0)
    assert compared.flag_differs == 1
    assert compared.flag_differs_boards == ["two"]
    assert compared.regions_differ == 1
    assert compared.score_difference.maximum == pytest.approx(0.5)
    assert compared.worst[0].image_id == "one"
    assert compared.map_difference_max is None


def test_the_largest_map_difference_is_found_where_both_runs_have_maps(tmp_path: Path) -> None:
    """Scores can agree while a map does not; this is what says so."""
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a, [_entry("one", 1.0)])
    _run(b, [_entry("one", 1.0)])
    for root, value in ((a, 0.0), (b, 0.25)):
        (root / "one").mkdir()
        np.save(root / "one" / MAP_NAME, np.full((4, 4), value, dtype=np.float32))

    assert compare_part("pcb1", a, b).map_difference_max == pytest.approx(0.25)


def test_runs_of_different_boards_are_refused(tmp_path: Path) -> None:
    """A comparison over a part of the boards would read as agreement it has not earned."""
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a, [_entry("one", 1.0)])
    _run(b, [_entry("two", 1.0)])
    with pytest.raises(ValueError, match="same boards"):
        compare_part("pcb1", a, b)


def test_banks_are_compared_row_by_row() -> None:
    """A row found in the other bank is the same patch, whatever its place there."""
    a = torch.tensor([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    b = torch.tensor([[0.0, 10.0], [0.0, 0.0], [50.0, 50.0]])

    compared = compare_banks(a, b)

    assert (compared.rows_a, compared.rows_b) == (3, 3)
    assert compared.same_rows == 2
    assert compared.nearest_distance.maximum == pytest.approx(10.0)
    assert compared.picks_in_step == 0


def test_the_picks_in_step_count_up_to_the_first_difference_in_order() -> None:
    """Rows are in the order the coreset chose them, so the first difference is where it parted."""
    a = torch.tensor([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [4.0, 0.0]])
    b = torch.tensor([[1.0, 0.0], [2.0, 0.0], [4.0, 0.0], [3.0, 0.0]])

    assert compare_banks(a, b).picks_in_step == 2
    assert compare_banks(a, a).picks_in_step == 4


def test_identical_rows_are_the_same_row_at_a_real_banks_magnitude() -> None:
    """A matrix product's float32 noise must not read as two patches being different."""
    torch.manual_seed(0)
    a = torch.rand(64, 1536) * 30
    b = a[torch.randperm(64)]

    compared = compare_banks(a, b)

    assert compared.same_rows == 64
    assert compared.nearest_distance.maximum == 0


def test_each_part_goes_through_the_laptops_steps_on_the_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Warm up, then train, score and bench each part; the record is written after each."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def through(part: str, **options: Any) -> None:  # noqa: ANN401
        calls.append((part, options))

    monkeypatch.setattr(card_run, "train_and_score", through)
    monkeypatch.setattr(card_run, "warm_up_pytorch", lambda _device: 1.5)
    monkeypatch.setattr(card_run, "own_card_reader", lambda: lambda: GpuReading(3, 2))
    out = tmp_path / "card.json"

    record = run_pytorch(
        ("pcb1", "pcb2"),
        visa_dir=tmp_path / "v",
        models_dir=tmp_path / "m",
        runs_dir=tmp_path / "r",
        out=out,
    )

    assert record.warm_up_seconds == [1.5, 1.5]
    assert [stage.name for stage in record.parts["pcb2"]] == ["train", "score", "bench"]
    assert [part for part, _ in calls] == ["pcb1"] * 3 + ["pcb2"] * 3
    train, score, bench = (options for _, options in calls[:3])
    assert train["infer"] is False
    assert "reuse" not in train
    assert score["reuse"] is True
    assert "infer" not in score
    assert (bench["reuse"], bench["infer"], bench["bench"]) == (True, False, True)
    assert all(options["device"] == "xpu" for _, options in calls)
    assert CardRun.model_validate_json(out.read_text(encoding="utf-8")) == record


class _Graph:
    def __init__(self, batch_size: int) -> None:
        self.batch_size = batch_size

    def __call__(self, batch: Any) -> tuple[Any, Any]:  # noqa: ANN401
        assert batch.shape[0] == self.batch_size
        count = batch.shape[0]
        return np.full(count, 3.0, dtype=np.float32), np.zeros(
            (count, 1, 256, 256), dtype=np.float32
        )


def _items(directory: Path) -> list[InferenceItem]:
    directory.mkdir()
    items: list[InferenceItem] = []
    for index in range(3):
        path = directory / f"{index}.png"
        Image.fromarray(np.full((64, 64, 3), index, dtype=np.uint8)).save(path)
        items.append(InferenceItem(image_id=f"good-{index}", path=path, label="good"))
    return items


def test_each_part_is_exported_scored_and_measured_at_each_batch_with_one_graph_on_the_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scored run is at batch 16; the bench record merges the two batches, 1 first as ever."""
    loaded: list[int] = []
    exported: list[tuple[str, int]] = []

    def load(_models: Path, part: str, *, batch_size: int, device: str) -> OpenVinoModel:
        assert device == "GPU.0"
        loaded.append(batch_size)
        return OpenVinoModel(
            _Graph(batch_size),
            train_record(part),
            batch_size=batch_size,
            resident_bytes=668,
            properties={"device_name": "Fake", "precision": "f32"},
        )

    def export(_models: Path, part: str, *, batch_size: int) -> None:
        exported.append((part, batch_size))

    items = _items(tmp_path / "images")
    monkeypatch.setattr(card_run.OpenVinoModel, "load", staticmethod(load))
    monkeypatch.setattr(card_run, "export_openvino", export)
    monkeypatch.setattr(card_run, "visa_test_items", lambda _visa, _part: items)
    monkeypatch.setattr(card_run, "own_card_reader", lambda: lambda: GpuReading(3, 2))
    monkeypatch.setattr(card_run, "measure", _measuring_without_workers(card_run.measure))
    runs = tmp_path / "runs"

    record = run_openvino(
        ("pcb4",),
        visa_dir=tmp_path / "v",
        models_dir=tmp_path / "m",
        runs_dir=runs,
        out=tmp_path / "card.json",
    )

    assert loaded == [16, 1]
    assert exported == [("pcb4", 16), ("pcb4", 1)]
    assert [stage.name for stage in record.parts["pcb4"]] == [
        "export-batch-16",
        "compile-batch-16",
        "first-use-batch-16",
        "score",
        "bench-batch-16",
        "export-batch-1",
        "compile-batch-1",
        "first-use-batch-1",
        "bench-batch-1",
    ]
    assert record.properties["precision"] == "f32"
    assert load_run_index(runs / "pcb4" / OPENVINO_RUN).images == 3
    bench = InferenceBench.model_validate_json(
        (runs / "pcb4" / OPENVINO_BENCH).read_text(encoding="utf-8")
    )
    assert [run.batch_size for run in bench.runs] == [1, 1, 16, 16]
    assert len(record.warm_up_seconds) == 2


def _measuring_without_workers(measure: Any) -> Any:  # noqa: ANN401
    def measuring(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        return measure(*args, num_workers=0, repeats=1, **kwargs)

    return measuring


def test_no_parts_is_refused(tmp_path: Path) -> None:
    """An empty run would write a record that reads as a measurement."""
    with pytest.raises(ValueError, match="no parts"):
        run_openvino(
            (),
            visa_dir=tmp_path,
            models_dir=tmp_path,
            runs_dir=tmp_path,
            out=tmp_path / "card.json",
        )


def test_the_compare_command_writes_its_record(tmp_path: Path) -> None:
    """Two roots and a run name each; every part named is compared."""
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a / "pcb1" / "test", [_entry("one", 1.0)])
    _run(b / "pcb1" / OPENVINO_RUN, [_entry("one", 1.25)])
    out = tmp_path / "out" / "scores.json"

    result = CliRunner().invoke(
        card_run.app,
        [
            "compare",
            "--a",
            str(a),
            "--b",
            str(b),
            "--b-batch",
            OPENVINO_RUN,
            "--a-label",
            "first",
            "--part",
            "pcb1",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    stored = Comparison.model_validate_json(out.read_text(encoding="utf-8"))
    assert stored.a == "first"
    assert stored.b == str(b)
    assert stored.parts["pcb1"].score_difference.maximum == pytest.approx(0.25)


def test_the_boards_command_writes_one_line_to_a_board_with_each_runs_figures(
    tmp_path: Path,
) -> None:
    """Scores keep every digit they were recorded with, so a difference can be worked again."""
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a / "pcb1" / "test", [_entry("one", 1.5, flagged=True, regions=2)])
    _run(b / "pcb1" / "test", [_entry("one", 1.25)])
    out = tmp_path / "boards.csv"

    result = CliRunner().invoke(
        card_run.app,
        [
            "boards",
            "--source",
            f"a={a}/{{part}}/test",
            "--source",
            f"b={b}/{{part}}/test",
            "--part",
            "pcb1",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.read_text(encoding="utf-8").splitlines() == [
        "part,image_id,label,a_score,a_flagged,a_regions,b_score,b_flagged,b_regions",
        "pcb1,one,good,1.5,1,2,1.25,0,0",
    ]


@pytest.mark.xpu
def test_on_the_card_the_warm_up_runs_and_leaves_nothing_behind() -> None:
    """A small embedding, coreset and scoring pass, off the card when it returns."""
    assert warm_up_pytorch("xpu", images=4) > 0
    assert torch.xpu.memory_allocated(0) == 0
