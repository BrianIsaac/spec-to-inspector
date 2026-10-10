"""Tests for the `correct` verb and for `inspect`'s corrections switch, end to end.

A fake VLM server answers; the runs are written by the real inference writer
with a stub anomaly model; the store is the real SQLite file under the
settings' runs directory.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.cli import app
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.judge.prompt import NO_CORRECTIONS
from spec_to_inspector.spec.schema import write_clause_table
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

runner = CliRunner()

SCRATCH = json.dumps(
    {
        "reason": "a thin bright line on the board face",
        "defect_class": "scratch",
        "clause_id": "4.1",
    }
)
MISSING = json.dumps(
    {"reason": "a bare pad where a part should be", "defect_class": "missing", "clause_id": "4.2"}
)
RENDERED = (
    "On a pcb9 board the judge called the flagged area 'scratch' (clause 4.1); "
    "the engineer corrected it to 'missing' (clause 4.2). "
    "The engineer's note: the pad is bare."
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
    monkeypatch.delenv("SPEC_TO_INSPECTOR_CORRECTIONS_DB", raising=False)
    monkeypatch.delenv("SPEC_TO_INSPECTOR_CORRECTIONS_RECALL", raising=False)
    monkeypatch.setattr(cli.out, "width", 400)
    monkeypatch.setattr(cli.err, "width", 400)
    path = tmp_path / "spec.clauses.json"
    write_clause_table(specification(), path)
    return path


@pytest.fixture
def run(tmp_path: Path) -> Path:
    """A run of two flagged boards and a good one.

    Returns:
        The run's directory.
    """
    return write_run(tmp_path / "u2", {"scratch": "scratch", "speck": "speck", "good": "good"})


def _store(tmp_path: Path) -> CorrectionStore:
    return CorrectionStore(tmp_path / "runs" / "corrections.sqlite3")


def _inspect(run: Path, spec_path: Path, server: FakeVlm, *more: str) -> Any:  # noqa: ANN401
    return runner.invoke(
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
            *more,
        ],
    )


def _correct(run: Path, spec_path: Path, *more: str) -> Any:  # noqa: ANN401
    return runner.invoke(app, ["correct", "--run", str(run), "--spec", str(spec_path), *more])


def _slot(request: dict[str, Any]) -> str:
    text = request["messages"][1]["content"][0]["text"]
    start = text.index("Corrections recorded by engineers")
    return text[text.index("\n", start) + 1 : text.index("What the inspector measured")].strip()


def test_an_override_from_the_command_line_changes_the_next_prompt(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """Inspect, correct, inspect the next board: its prompt quotes the engineer."""
    with FakeVlm(default=SCRATCH) as server:
        first = _inspect(run, spec_path, server, "--image-id", "scratch")
        corrected = _correct(
            run, spec_path, "--image-id", "scratch", "--clause", "4.2", "--note", "the pad is bare"
        )
        second = _inspect(run, spec_path, server, "--image-id", "speck")

    assert first.exit_code == 0, first.output
    assert corrected.exit_code == 0, corrected.output
    assert second.exit_code == 0, second.output
    assert _slot(server.requests[0]) == NO_CORRECTIONS
    assert _slot(server.requests[1]) == f"1. {RENDERED}"
    store = _store(tmp_path)
    assert corrected.stdout.splitlines() == [
        f"Recorded correction 1 of scratch, region 1, in {store.path}",
        RENDERED,
    ]
    (kept,) = store.for_image("pcb9", "scratch")
    assert (kept.judged_class, kept.corrected_class, kept.note) == (
        "scratch",
        "missing",
        "the pad is bare",
    )
    assert load_decision(run / "scratch").corrected.overridden
    assert load_decision(run / "speck").corrected.in_prompt
    assert f"Corrections: 1 recorded in {store.path}" in second.stderr
    assert "Corrections" not in first.stderr


def test_no_corrections_leaves_the_slot_empty_whatever_the_store_holds(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """The one switch the bench uses: the store is there, and the judge is not shown it."""
    with FakeVlm(default=SCRATCH) as server:
        _inspect(run, spec_path, server, "--image-id", "scratch")
        _correct(run, spec_path, "--image-id", "scratch", "--clause", "4.2")
        result = _inspect(run, spec_path, server, "--no-corrections")

    assert result.exit_code == 0, result.output
    assert [_slot(request) for request in server.requests] == [NO_CORRECTIONS] * 3
    assert "Corrections" not in result.stderr
    again = load_decision(run / "scratch")
    assert not again.corrected.in_prompt
    assert again.corrected.overridden, "the image is still the one an engineer overrode"
    assert _store(tmp_path).count() == 1


def test_an_empty_store_is_not_created_by_inspecting(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """With nothing recorded the default is off, asked for or not, and no file appears."""
    with FakeVlm(default=SCRATCH) as server:
        default = _inspect(run, spec_path, server, "--image-id", "scratch")
        asked = _inspect(run, spec_path, server, "--image-id", "scratch", "--corrections")

    assert default.exit_code == 0, default.output
    assert asked.exit_code == 0, asked.output
    assert [_slot(request) for request in server.requests] == [NO_CORRECTIONS] * 2
    assert not _store(tmp_path).path.exists()


def test_the_recall_strategy_and_the_stores_file_come_from_the_settings(
    spec_path: Path, run: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recall on the answer asks a second question where a correction matches."""
    elsewhere = tmp_path / "demo" / "corrections.sqlite3"
    monkeypatch.setenv("SPEC_TO_INSPECTOR_CORRECTIONS_DB", str(elsewhere))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_CORRECTIONS_RECALL", "answer")
    with FakeVlm([SCRATCH, SCRATCH, MISSING]) as server:
        _inspect(run, spec_path, server, "--image-id", "scratch")
        corrected = _correct(
            run, spec_path, "--image-id", "scratch", "--clause", "4.2", "--note", "the pad is bare"
        )
        result = _inspect(run, spec_path, server, "--image-id", "speck")

    assert corrected.exit_code == 0, corrected.output
    assert result.exit_code == 0, result.output
    assert CorrectionStore(elsewhere).count() == 1
    assert not _store(tmp_path).path.exists()
    assert [_slot(request) for request in server.requests] == [
        NO_CORRECTIONS,
        NO_CORRECTIONS,
        f"1. {RENDERED}",
    ]
    speck = load_decision(run / "speck")
    assert speck.regions[0].first_answer is not None
    assert speck.regions[0].first_answer.clause_id == "4.1"
    assert speck.regions[0].answer is not None
    assert speck.regions[0].answer.clause_id == "4.2"
    assert "on its own answer" in result.stderr


def test_a_false_alarm_is_corrected_to_no_defect(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """--no-defect records that no clause applies."""
    with FakeVlm(default=SCRATCH) as server:
        _inspect(run, spec_path, server, "--image-id", "speck")
    result = _correct(run, spec_path, "--image-id", "speck", "--no-defect", "--note", "glare")

    assert result.exit_code == 0, result.output
    (kept,) = _store(tmp_path).for_image("pcb9", "speck")
    assert kept.corrected_class is None
    assert kept.corrected_clause is None
    assert result.stdout.splitlines()[1].endswith(
        "the engineer corrected it to no defect: no clause applies. The engineer's note: glare."
    )


def test_a_region_and_a_class_can_be_named(spec_path: Path, tmp_path: Path) -> None:
    """--region picks another region than the deciding one; --defect-class is checked."""
    run = write_run(tmp_path / "u2", {"two": "two"})
    with FakeVlm(default=SCRATCH) as server:
        _inspect(run, spec_path, server)
    result = _correct(
        run, spec_path, "--image-id", "two", "--region", "1", "--clause", "4.2",
        "--defect-class", "missing",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    (kept,) = _store(tmp_path).for_image("pcb9", "two")
    assert kept.region_index == 1
    assert kept.crop_path == str((run / "two" / "crops" / "region-001.png").resolve())


@pytest.mark.parametrize(
    ("options", "problem"),
    [
        (["--image-id", "scratch"], "give the clause with --clause, or --no-defect"),
        (["--image-id", "scratch", "--clause", "4.2", "--no-defect"], "not both"),
        (["--image-id", "scratch", "--defect-class", "missing", "--no-defect"], "not both"),
        (["--clause", "4.2"], "Missing option '--image-id'"),
    ],
)
def test_a_correction_that_does_not_say_what_it_corrects_to_is_a_usage_error(
    spec_path: Path, run: Path, tmp_path: Path, options: list[str], problem: str
) -> None:
    """Neither a clause nor --no-defect, or both, or no image: exit 2, nothing stored."""
    result = _correct(run, spec_path, *options)

    assert result.exit_code == 2
    assert problem in result.output
    assert not _store(tmp_path).path.exists()


def test_what_cannot_be_overridden_fails_with_the_cause(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """An image not judged, not in the run, a clause not in the table, a directory not a run."""
    with FakeVlm(default=SCRATCH) as server:
        _inspect(run, spec_path, server, "--image-id", "scratch", "--image-id", "good")
    cases = [
        (["--image-id", "speck", "--clause", "4.2"], "holds no decision; judge it first"),
        (["--image-id", "nowhere", "--clause", "4.2"], f"the run {run} holds no image nowhere"),
        (["--image-id", "scratch", "--clause", "9.9"], "part pcb9 has no clause 9.9"),
        (["--image-id", "scratch", "--clause", "4.1"], "repeats the judge's own answer"),
        (["--image-id", "scratch", "--clause", "4.2", "--region", "2"], "was not judged"),
        (["--image-id", "good", "--clause", "4.2"], "no flagged area of good was judged"),
    ]
    for options, problem in cases:
        result = _correct(run, spec_path, *options)
        assert result.exit_code == 1, (options, result.output)
        assert problem in result.stderr, (options, result.stderr)

    not_a_run = runner.invoke(
        app,
        ["correct", "--run", str(tmp_path), "--spec", str(spec_path), "--image-id", "x",
         "--clause", "4.2"],
    )  # fmt: skip
    assert not_a_run.exit_code == 1
    assert "is not a run" in not_a_run.stderr
    no_spec = runner.invoke(
        app,
        ["correct", "--run", str(run), "--spec", "nowhere.json", "--image-id", "scratch",
         "--clause", "4.2"],
    )  # fmt: skip
    assert no_spec.exit_code == 1
    assert "cannot read the specification" in no_spec.stderr
    assert not _store(tmp_path).path.exists()


def test_a_file_that_is_not_a_store_fails_both_verbs_in_words(
    spec_path: Path, run: Path, tmp_path: Path
) -> None:
    """A damaged store stops the command; it is neither ignored nor overwritten."""
    with FakeVlm(default=SCRATCH) as server:
        _inspect(run, spec_path, server, "--image-id", "scratch")
        path = _store(tmp_path).path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not a database, and long enough to be read as a header by SQLite\n" * 4)
        inspected = _inspect(run, spec_path, server, "--image-id", "speck")
    corrected = _correct(run, spec_path, "--image-id", "scratch", "--clause", "4.2")

    assert inspected.exit_code == 1
    assert "is not a corrections store" in inspected.stderr
    assert corrected.exit_code == 1
    assert "is not a corrections store" in corrected.stderr
    assert not load_decision(run / "scratch").corrected.overridden
