"""Tests for the command line entry point."""

import sys
from functools import partial
from pathlib import Path

import pytest
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.anomaly import pipeline, results
from spec_to_inspector.anomaly.pipeline import CategoryOutcome
from spec_to_inspector.anomaly.records import InferenceOptions
from spec_to_inspector.anomaly.split import SplitError
from spec_to_inspector.cli import app
from spec_to_inspector.datasets.visa import MANIFEST_NAME, fetch_visa
from tests.anomaly.records_fakes import inference_bench, run_index, train_record
from tests.datasets.visa_fakes import EXPECTED, NO_WAIT, FakeServer, fake_files, make_tar

runner = CliRunner()


def test_help_lists_every_verb() -> None:
    """The top-level help names the six verbs of the pipeline."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for verb in ("data", "parse", "train", "inspect", "bench", "serve"):
        assert verb in result.output


@pytest.mark.parametrize(
    ("verb", "unit"),
    [("parse", "U3"), ("inspect", "U5"), ("bench", "U7"), ("serve", "U8")],
)
def test_stubbed_verbs_fail_and_name_their_unit(verb: str, unit: str) -> None:
    """A verb not built yet exits non-zero and says which unit builds it."""
    result = runner.invoke(app, [verb])

    assert result.exit_code == 1
    assert "not built yet" in result.output
    assert unit in result.output


def test_data_help_lists_fetch() -> None:
    """The data group offers the fetch command."""
    result = runner.invoke(app, ["data", "--help"])

    assert result.exit_code == 0
    assert "fetch" in result.output


@pytest.fixture
def data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the settings at a temporary data directory and the fetch at a fake server.

    Returns:
        The data directory.
    """
    server = FakeServer(make_tar(fake_files()), drops=[])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.out, "width", 240)
    monkeypatch.setattr(cli.err, "width", 240)
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        cli,
        "fetch_visa",
        partial(
            fetch_visa,
            expected=EXPECTED,
            expected_bytes=len(server.body),
            transport=server.transport(),
            retry_delays=NO_WAIT,
        ),
    )
    return tmp_path / "data"


def test_data_fetch_streams_verifies_and_prints_the_counts(data_dir: Path) -> None:
    """A first fetch reports the counts per category and where the manifest is."""
    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    assert (data_dir / "visa" / MANIFEST_NAME).is_file()
    assert "Streamed" in result.output
    assert "pcb4" in result.output
    assert "wrong place 1" in result.output
    assert MANIFEST_NAME in result.output


def test_data_fetch_twice_re_verifies(data_dir: Path) -> None:
    """A second fetch re-verifies and says so."""
    runner.invoke(app, ["data", "fetch"])

    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    assert "Re-verified" in result.output


def test_data_fetch_fails_on_a_changed_tree_and_names_the_way_out(data_dir: Path) -> None:
    """A changed file makes the fetch exit 1 with the difference and the --force hint."""
    runner.invoke(app, ["data", "fetch"])
    (data_dir / "visa/pcb1/Data/Images/Normal/0000.JPG").write_bytes(b"changed")

    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 1
    assert "tree digest differs" in result.output
    assert "--force" in result.output


def test_data_fetch_reports_progress_in_tenths_without_a_terminal(data_dir: Path) -> None:
    """Without a terminal the bar is hidden, so plain lines mark each tenth of the stream."""
    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    tenths = [line for line in result.output.splitlines() if line.startswith("Received ")]
    assert len(tenths) == 10
    assert tenths[-1].endswith("(100%)")


class _TrainCalls:
    """Stands in for the anomaly pipeline, recording each category it is asked for."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: Exception | None = None
        self.auroc = {"pcb1": 0.951, "pcb2": 0.93, "pcb3": 0.9, "pcb4": 0.9857}

    def train_and_score(
        self,
        category: str,
        *,
        visa_dir: Path,
        models_dir: Path,
        runs_dir: Path,
        reuse: bool,
        infer: bool,
        bench: bool,
        seed: int,
        backbone: str,
        options: InferenceOptions | None = None,
    ) -> CategoryOutcome:
        if self.error is not None:
            raise self.error
        self.calls.append(
            {
                "category": category,
                "visa_dir": visa_dir,
                "models_dir": models_dir,
                "runs_dir": runs_dir,
                "reuse": reuse,
                "infer": infer,
                "bench": bench,
                "seed": seed,
                "backbone": backbone,
            }
        )
        return CategoryOutcome(
            category=category,
            trained=not reuse,
            record=train_record(category, image_auroc=self.auroc[category], seed=seed),
            run=run_index(category, image_auroc=self.auroc[category]) if infer else None,
            run_dir=runs_dir / category / "test" if infer else None,
            bench=inference_bench(category) if bench else None,
        )


@pytest.fixture
def training(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _TrainCalls:
    """Replace the anomaly pipeline with a recorder and run from a temporary directory.

    Returns:
        The recorder.
    """
    calls = _TrainCalls()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.out, "width", 240)
    monkeypatch.setattr(cli.err, "width", 240)
    monkeypatch.setattr(pipeline, "train_and_score", calls.train_and_score)
    return calls


def test_train_needs_a_category_or_all(training: _TrainCalls) -> None:
    """Without a category the verb explains itself and trains nothing."""
    result = runner.invoke(app, ["train"])

    assert result.exit_code == 2
    assert "--category" in result.output
    assert "--all" in result.output
    assert training.calls == []


def test_train_refuses_both_a_category_and_all(training: _TrainCalls) -> None:
    """A category and --all together are ambiguous."""
    result = runner.invoke(app, ["train", "--category", "pcb4", "--all"])

    assert result.exit_code == 2
    assert training.calls == []


def test_train_refuses_an_unknown_category(training: _TrainCalls) -> None:
    """A category VisA's PCB set does not hold is named, with the four that it does."""
    result = runner.invoke(app, ["train", "--category", "candle"])

    assert result.exit_code == 2
    assert "candle" in result.output
    assert "pcb1, pcb2, pcb3, pcb4" in result.output
    assert training.calls == []


def test_train_one_category_uses_the_settings_directories(
    training: _TrainCalls, tmp_path: Path
) -> None:
    """One category is trained and scored under data/, models/ and runs/ of the settings."""
    result = runner.invoke(app, ["train", "--category", "pcb4"])

    assert result.exit_code == 0, result.output
    assert training.calls == [
        {
            "category": "pcb4",
            "visa_dir": Path("data/visa"),
            "models_dir": Path("models"),
            "runs_dir": Path("runs"),
            "reuse": False,
            "infer": True,
            "bench": False,
            "seed": 0,
            "backbone": "wide_resnet50_2",
        }
    ]


def test_train_reports_the_auroc_against_the_reference_and_the_gate(
    training: _TrainCalls,
) -> None:
    """The table shows the measured AUROC, the published figure, the gap and the gate."""
    result = runner.invoke(app, ["train", "--category", "pcb4"])

    assert result.exit_code == 0, result.output
    assert "98.57" in result.output
    assert "99.0" in result.output
    assert "-0.43" in result.output
    assert "within" in result.output
    assert "ResNet18" in result.output
    assert "models/patchcore/pcb4" in result.output
    assert "runs/pcb4/test" in result.output


def test_train_says_where_the_thresholds_were_chosen(training: _TrainCalls) -> None:
    """When the thresholds come from the test split, the output says so in words."""
    result = runner.invoke(app, ["train", "--category", "pcb4"])

    assert "chosen on the test split" in result.output
    assert "AUROC" in result.output


def test_train_all_runs_the_four_pcb_categories_in_order(training: _TrainCalls) -> None:
    """--all means pcb1 to pcb4."""
    result = runner.invoke(app, ["train", "--all"])

    assert result.exit_code == 0, result.output
    assert [call["category"] for call in training.calls] == ["pcb1", "pcb2", "pcb3", "pcb4"]


def test_train_names_a_category_outside_the_gate(training: _TrainCalls) -> None:
    """A category more than 3 points under its reference is flagged, and the exit stays 0."""
    result = runner.invoke(app, ["train", "--category", "pcb3"])

    assert result.exit_code == 0, result.output
    assert "-9.00" in result.output
    assert "more than 3 points under" in result.output
    assert "pcb3" in result.output


def test_train_takes_its_roots_and_switches_from_the_command_line(
    training: _TrainCalls, tmp_path: Path
) -> None:
    """The output roots, reuse, the seed and leaving inference out are options."""
    result = runner.invoke(
        app,
        [
            "train",
            "--category",
            "pcb1",
            "--category",
            "pcb2",
            "--models-dir",
            str(tmp_path / "m"),
            "--runs-dir",
            str(tmp_path / "r"),
            "--reuse",
            "--no-infer",
            "--seed",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert [call["category"] for call in training.calls] == ["pcb1", "pcb2"]
    assert training.calls[0]["models_dir"] == tmp_path / "m"
    assert training.calls[0]["runs_dir"] == tmp_path / "r"
    assert training.calls[0]["reuse"] is True
    assert training.calls[0]["infer"] is False
    assert training.calls[0]["seed"] == 7
    assert "reused" in result.output


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("CUDA is not available: check the driver"),
        SplitError("data/visa/split_csv/1cls.csv is missing: run `spec-to-inspector data fetch`"),
    ],
)
def test_train_fails_with_the_cause(training: _TrainCalls, error: Exception) -> None:
    """A missing GPU or missing data ends the verb with exit 1 and the reason."""
    training.error = error

    result = runner.invoke(app, ["train", "--category", "pcb4"])

    assert result.exit_code == 1
    assert str(error).split(":")[0] in result.output


def test_train_bench_measures_throughput_and_prints_it(training: _TrainCalls) -> None:
    """--bench asks for the throughput measurement and reports images per second."""
    result = runner.invoke(app, ["train", "--category", "pcb4", "--bench"])

    assert result.exit_code == 0, result.output
    assert training.calls[0]["bench"] is True
    assert "images/s" in result.output
    assert "100.5" in result.output
    assert "40.2" in result.output
    assert "runs/pcb4/bench.json" in result.output


def test_train_results_writes_the_tracked_figures(
    training: _TrainCalls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--results collects the categories' records from disk into the file named."""
    asked: list[tuple[tuple[str, ...], Path, Path]] = []

    def collect(
        categories: tuple[str, ...], *, models_dir: Path, runs_dir: Path, written_by: list[str]
    ) -> results.AnomalyResults:
        asked.append((tuple(categories), models_dir, runs_dir))
        return results.AnomalyResults(
            created_at="2026-10-10T13:00:00+00:00",
            written_by=written_by,
            outside_gate=[],
            thresholds_tuned_on_test=True,
            categories={},
        )

    monkeypatch.setattr(results, "collect", collect)
    target = tmp_path / "results" / "stage1" / "anomaly.json"
    arguments = ["train", "--all", "--reuse", "--results", str(target)]
    monkeypatch.setattr(sys, "argv", ["/venv/bin/spec-to-inspector", *arguments])

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    assert asked == [(("pcb1", "pcb2", "pcb3", "pcb4"), Path("models"), Path("runs"))]
    written = results.AnomalyResults.model_validate_json(target.read_text())
    assert written.written_by[0] == "spec-to-inspector"
    assert written.written_by[1:] == ["train", "--all", "--reuse", "--results", str(target)]
    assert str(target) in result.output


def test_train_another_backbone_needs_its_own_models_directory(
    training: _TrainCalls, tmp_path: Path
) -> None:
    """A backbone other than the product's cannot land where the product's models live."""
    refused = runner.invoke(app, ["train", "--category", "pcb4", "--backbone", "resnet18"])

    assert refused.exit_code == 2
    assert "--models-dir" in refused.output
    assert training.calls == []

    same = runner.invoke(
        app, ["train", "--category", "pcb4", "--backbone", "resnet18", "--models-dir", "models"]
    )

    assert same.exit_code == 2
    assert training.calls == []

    accepted = runner.invoke(
        app,
        [
            "train",
            "--category",
            "pcb4",
            "--backbone",
            "resnet18",
            "--models-dir",
            str(tmp_path / "reference"),
            "--runs-dir",
            str(tmp_path / "reference-runs"),
        ],
    )

    assert accepted.exit_code == 0, accepted.output
    assert training.calls[0]["backbone"] == "resnet18"
    assert training.calls[0]["models_dir"] == tmp_path / "reference"
