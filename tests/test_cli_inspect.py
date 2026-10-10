"""Tests for the `inspect` verb, against a fake VLM server and a stub anomaly model."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.anomaly import infer
from spec_to_inspector.cli import app
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.spec.schema import write_clause_table
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import StubScorer, write_run
from tests.spec.spec_fakes import specification

runner = CliRunner()

REPLY = json.dumps(
    {
        "reason": "a thin bright line scored across the board face",
        "defect_class": "scratch",
        "clause_id": "4.1",
    }
)


@pytest.fixture
def spec_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Write the fake specification and run from a temporary directory with wide consoles.

    Returns:
        The clause table's path.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPEC_TO_INSPECTOR_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(cli.out, "width", 400)
    monkeypatch.setattr(cli.err, "width", 400)
    path = tmp_path / "spec.clauses.json"
    write_clause_table(specification(), path)
    return path


def _lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.strip()]


def test_a_run_directory_is_judged_and_each_image_gets_one_line(
    spec_path: Path, tmp_path: Path
) -> None:
    """Every image of the run gets a decision file and a one-line verdict."""
    run = write_run(tmp_path / "u2", {"good": "good", "speck": "speck", "scratch": "scratch"})
    with FakeVlm(default=REPLY) as server:
        result = runner.invoke(
            app,
            [
                "inspect",
                "--category",
                "pcb9",
                "--run",
                str(run),
                "--spec",
                str(spec_path),
                "--url",
                server.url,
                "--model",
                "fake-vlm",
            ],
        )

    assert result.exit_code == 0, result.output
    lines = _lines(result.stdout)
    assert lines[0].startswith("good: accept: the anomaly score 10.000 is not above")
    assert lines[1].startswith("speck: accept, clause 4.1.2 Scratch (page 3): every flagged area")
    assert lines[2].startswith("scratch: reject, clause 4.1.1 Scratch (page 3): region 1: longest")
    assert lines[3] == f"3 images: 2 accept, 1 reject, 0 needs review. Decisions: {run}"
    assert len(lines) == 4
    assert load_decision(run / "scratch").outcome is Outcome.REJECT
    assert load_decision(run / "scratch").judge_model == "fake-vlm"
    assert all(request["model"] == "fake-vlm" for request in server.requests)


def test_images_are_scored_by_the_anomaly_model_first(
    spec_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given image files, the verb scores them into a run of its own and judges that."""
    loaded: list[tuple[Path, str]] = []

    def load(models_dir: Path, category: str) -> StubScorer:
        loaded.append((models_dir, category))
        return StubScorer()

    monkeypatch.setattr(infer.AnomalyModel, "load", load)
    boards = {"line-3-0001": 140, "line-3-0002": 20}
    paths: list[str] = []
    for name, red in boards.items():
        colour = np.zeros((800, 1000, 3), dtype=np.uint8)
        colour[..., 0] = red
        colour[..., 1] = 110
        Image.fromarray(colour).save(tmp_path / f"{name}.png")
        paths.append(str(tmp_path / f"{name}.png"))

    with FakeVlm(default=REPLY) as server:
        result = runner.invoke(
            app,
            [
                "inspect",
                "--category",
                "pcb9",
                *paths,
                "--spec",
                str(spec_path),
                "--url",
                server.url,
            ],
        )

    assert result.exit_code == 0, result.output
    assert loaded == [(tmp_path / "models", "pcb9")]
    run = tmp_path / "runs" / "pcb9" / "inspect"
    assert load_decision(run / "line-3-0001").outcome is Outcome.REJECT
    assert load_decision(run / "line-3-0002").outcome is Outcome.ACCEPT
    lines = _lines(result.stdout)
    assert lines[0].startswith("line-3-0001: reject, clause 4.1.1 Scratch (page 3)")
    assert lines[1].startswith("line-3-0002: accept")
    assert lines[2].endswith(f"Decisions: {run}")


def test_the_batch_name_places_the_run(
    spec_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch of images lands in a run directory of the name given."""
    monkeypatch.setattr(infer.AnomalyModel, "load", lambda *_: StubScorer())
    colour = np.zeros((800, 1000, 3), dtype=np.uint8)
    Image.fromarray(colour).save(tmp_path / "board.png")

    with FakeVlm(default=REPLY) as server:
        result = runner.invoke(
            app,
            [
                "inspect",
                "-c",
                "pcb9",
                str(tmp_path / "board.png"),
                "--batch",
                "line-3",
                "--spec",
                str(spec_path),
                "--url",
                server.url,
            ],
        )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "runs" / "pcb9" / "line-3" / "board" / "decision.json").is_file()


def test_the_server_and_the_model_default_to_the_settings(
    spec_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --url and --model the settings' backend is asked."""
    run = write_run(tmp_path / "u2", {"scratch": "scratch"})
    with FakeVlm(default=REPLY) as server:
        monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_URL", server.url)
        monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_MODEL", "from-settings")
        result = runner.invoke(
            app, ["inspect", "--category", "pcb9", "--run", str(run), "--spec", str(spec_path)]
        )

    assert result.exit_code == 0, result.output
    assert server.requests[0]["model"] == "from-settings"


def test_named_images_of_a_run_and_a_region_limit(spec_path: Path, tmp_path: Path) -> None:
    """--image-id judges part of a run; --max-regions bounds the questions per image."""
    run = write_run(tmp_path / "u2", {"good": "good", "two": "two", "scratch": "scratch"})
    with FakeVlm(default=REPLY) as server:
        result = runner.invoke(
            app,
            [
                "inspect",
                "--category",
                "pcb9",
                "--run",
                str(run),
                "--image-id",
                "two",
                "--max-regions",
                "1",
                "--spec",
                str(spec_path),
                "--url",
                server.url,
            ],
        )

    assert result.exit_code == 0, result.output
    lines = _lines(result.stdout)
    assert lines[0].startswith("two: needs review: the 1 flagged area judged is within its clause")
    assert lines[1].startswith("1 image: 0 accept, 0 reject, 1 needs review.")
    assert len(server.requests) == 1
    assert not (run / "scratch" / "decision.json").exists()


def test_a_server_that_is_down_refers_every_board_and_fails_the_command(
    spec_path: Path, tmp_path: Path
) -> None:
    """The decisions are still written, each a referral, and the exit code is not zero."""
    run = write_run(tmp_path / "u2", {"good": "good", "scratch": "scratch"})
    with FakeVlm() as server:
        url = server.url

    result = runner.invoke(
        app, ["inspect", "-c", "pcb9", "--run", str(run), "--spec", str(spec_path), "--url", url]
    )

    assert result.exit_code == 1
    lines = _lines(result.stdout)
    assert lines[0].startswith("good: accept")
    assert lines[1].startswith("scratch: needs review: region 1: the judge could not be asked")
    assert "1 of 2 images could not be put to the judge" in result.stderr
    assert load_decision(run / "scratch").outcome is Outcome.NEEDS_REVIEW


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "give image files or --run"),
        (["board.png", "--run", "runs/pcb9/test"], "give image files or --run"),
        (["--run", "runs/pcb9/test", "--batch", "line-3"], "--batch names the run"),
        (["board.png", "--image-id", "board"], "--image-id picks images of --run"),
    ],
)
def test_images_and_a_run_exclude_one_another(
    spec_path: Path, arguments: list[str], message: str
) -> None:
    """The verb takes image files or a run directory, and says so."""
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(spec_path.parent / "board.png")

    result = runner.invoke(
        app, ["inspect", "--category", "pcb9", *arguments, "--spec", str(spec_path)]
    )

    assert result.exit_code == 2
    assert message in result.output


def test_a_part_the_specification_does_not_cover_is_refused(spec_path: Path) -> None:
    """The error names the parts the document does cover."""
    result = runner.invoke(
        app, ["inspect", "--category", "pcb4", "--run", "anywhere", "--spec", str(spec_path)]
    )

    assert result.exit_code == 2
    assert "pcb9" in result.output


def test_a_run_of_another_part_is_refused(spec_path: Path, tmp_path: Path) -> None:
    """A pcb9 run is not judged as another part."""
    run = write_run(tmp_path / "u2", {"scratch": "scratch"})
    two_parts = specification(
        calibrations=(
            specification().calibrations[0],
            specification().calibrations[0].model_copy(update={"category": "pcb7"}),
        ),
        clauses=(
            *specification().clauses,
            specification()
            .clauses[2]
            .model_copy(update={"id": "5.1", "heading_id": "5.1", "category": "pcb7"}),
        ),
    )
    write_clause_table(two_parts, spec_path)

    result = runner.invoke(
        app, ["inspect", "--category", "pcb7", "--run", str(run), "--spec", str(spec_path)]
    )

    assert result.exit_code == 1
    assert "pcb9" in result.output
    assert "pcb7" in result.output


def test_a_specification_that_cannot_be_read_fails_with_the_cause(spec_path: Path) -> None:
    """A missing or broken clause table is reported, not traced."""
    missing = runner.invoke(
        app, ["inspect", "--category", "pcb9", "--run", "x", "--spec", "nowhere.json"]
    )
    spec_path.write_text('{"title": "half a specification"}')
    broken = runner.invoke(
        app, ["inspect", "--category", "pcb9", "--run", "x", "--spec", str(spec_path)]
    )

    assert missing.exit_code == 1
    assert "nowhere.json" in missing.output
    assert broken.exit_code == 1
    assert "not a valid clause table" in broken.output


def test_a_directory_that_is_not_a_run_fails_with_the_cause(
    spec_path: Path, tmp_path: Path
) -> None:
    """A path without `run.json` is named."""
    result = runner.invoke(
        app, ["inspect", "-c", "pcb9", "--run", str(tmp_path), "--spec", str(spec_path)]
    )

    assert result.exit_code == 1
    assert "run.json" in result.output


def test_images_without_a_trained_model_fail_with_the_way_out(
    spec_path: Path, tmp_path: Path
) -> None:
    """An untrained part names the command that trains it."""
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(tmp_path / "board.png")

    result = runner.invoke(
        app, ["inspect", "-c", "pcb9", str(tmp_path / "board.png"), "--spec", str(spec_path)]
    )

    assert result.exit_code == 1
    assert "spec-to-inspector train --category pcb9" in result.output


def test_two_images_of_one_name_are_refused(
    spec_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Image ids come from the file names, so two files of one name cannot share a run."""
    monkeypatch.setattr(infer.AnomalyModel, "load", lambda *_: StubScorer())
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    for folder in ("a", "b"):
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(tmp_path / folder / "board.png")

    result = runner.invoke(
        app,
        [
            "inspect",
            "-c",
            "pcb9",
            str(tmp_path / "a" / "board.png"),
            str(tmp_path / "b" / "board.png"),
            "--spec",
            str(spec_path),
        ],
    )

    assert result.exit_code == 1
    assert "board" in result.output


def test_a_server_that_dies_after_an_earlier_referral_still_fails_the_command(
    spec_path: Path, tmp_path: Path
) -> None:
    """The board's first referral may be the model's fault; a dead server behind it still counts."""
    run = write_run(tmp_path / "u2", {"two": "two"})
    unknown = json.dumps(json.loads(REPLY) | {"clause_id": "9.9"})
    with FakeVlm([unknown]) as server:
        result = runner.invoke(
            app,
            [
                "inspect",
                "-c",
                "pcb9",
                "--run",
                str(run),
                "--spec",
                str(spec_path),
                "--url",
                server.url,
            ],
        )

    assert result.exit_code == 1
    assert "1 of 1 images could not be put to the judge" in result.stderr
    assert _lines(result.stdout)[0].startswith("two: needs review: region 1: clause 9.9 is not")
