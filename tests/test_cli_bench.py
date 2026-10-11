"""Tests for the `bench` verb, against a stub anomaly model and a fake VLM server."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from spec_to_inspector import cli
from spec_to_inspector.anomaly.infer import visa_test_items
from spec_to_inspector.bench import run as benching
from spec_to_inspector.bench.record import read_record, write_record
from spec_to_inspector.cli import app
from spec_to_inspector.settings import Settings
from tests.bench.bench_fakes import (
    REPLIES,
    stub_models,
    stub_scoring,
    write_bench_labels,
    write_bench_visa,
)
from tests.bench.conftest import tracked
from tests.judge.fake_vlm import FakeVlm

ROOT = Path(__file__).parents[1]
RESULTS = Path("results/stage1/bench.json")
PAGE = Path("results/stage1/README.md")

runner = CliRunner()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Lay out a repository in miniature and stand the stub pipeline in for the laptop's.

    Returns:
        The working directory: `specs/`, `eval/`, the small VisA under
        `data/visa`, and nothing yet under `results/`.
    """
    monkeypatch.chdir(tmp_path)
    for name in ("DATA", "MODELS", "RUNS"):
        monkeypatch.setenv(f"SPEC_TO_INSPECTOR_{name}_DIR", str(tmp_path / name.lower()))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_MODEL", "fake-vlm")
    monkeypatch.setattr(cli.out, "width", 400)
    monkeypatch.setattr(cli.err, "width", 400)
    write_bench_visa(tmp_path / "data" / "visa")
    write_bench_labels(
        tmp_path / "data" / "visa", tmp_path / "runs", Path("eval/clause_labels.csv")
    )
    shutil.copy(ROOT / "eval" / "PROTOCOL.md", "eval/PROTOCOL.md")
    Path("specs").mkdir()
    for name in ("pcb-spec.pdf", "pcb-spec.clauses.json"):
        shutil.copy(ROOT / "specs" / name, Path("specs") / name)

    def pipeline(_settings: Settings) -> benching.Pipeline:
        return benching.Pipeline(
            parse=tracked, models=stub_models, test_items=visa_test_items, scoring=stub_scoring
        )

    monkeypatch.setattr(benching, "laptop_pipeline", pipeline)
    return tmp_path


def _bench(server: FakeVlm, *arguments: str) -> Result:
    return runner.invoke(app, ["bench", *arguments], env={"SPEC_TO_INSPECTOR_VLM_URL": server.url})


def test_the_verb_runs_the_set_and_writes_the_figures_and_the_page(world: Path) -> None:
    """One command: both parts scored and judged, `bench.json` and `README.md` written."""
    with FakeVlm(REPLIES) as server:
        result = _bench(server)
        assert all(request["cache_prompt"] is False for request in server.requests)

    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[0].startswith("Clause-citation accuracy, strict, 3 single-defect images: 66.7%")
    assert lines[-2:] == [f"Figures: {RESULTS}", f"Page: {PAGE}"]
    record = read_record(RESULTS)
    assert not record.partial
    assert record.repeat is None
    assert record.command == ["spec-to-inspector", "bench"]
    assert record.protocol.path == "eval/PROTOCOL.md"
    assert "66.7% (2 of 3)" in PAGE.read_text(encoding="utf-8")
    assert (world / "runs" / "pcb4" / "bench" / "bad-000" / "decision.json").is_file()
    assert "pcb4: scored 5 images" in result.stderr


def test_a_second_run_says_how_many_answers_differ_from_the_first(world: Path) -> None:
    """The record that replaces another of the same making carries the comparison."""
    with FakeVlm([*REPLIES, *REPLIES]) as server:
        assert _bench(server).exit_code == 0
        second = _bench(server)

    assert second.exit_code == 0, second.output
    repeat = read_record(RESULTS).repeat
    assert repeat is not None
    assert (repeat.areas_compared, repeat.heading_differs, repeat.sentence_differs) == (4, 0, 0)
    assert repeat.figures_equal
    assert "the figures are equal" in second.stdout
    assert "Every counted figure of the protocol is equal" in PAGE.read_text(encoding="utf-8")


def test_a_trial_run_must_name_its_own_results_and_writes_no_page(world: Path) -> None:
    """A cut-down run can never replace the tracked figures by default."""
    with FakeVlm(REPLIES[2:3]) as server:
        refused = _bench(server, "--limit", "1", "--part", "pcb4")
        assert server.requests == []
        made = _bench(
            server, "--limit", "1", "--part", "pcb4", "--results", "trial.json", "--batch", "trial"
        )

    assert refused.exit_code == 2
    assert "--results" in refused.output
    assert made.exit_code == 0, made.output
    trial = read_record(Path("trial.json"))
    assert trial.partial
    assert trial.command == [
        "spec-to-inspector",
        "bench",
        "--part",
        "pcb4",
        "--limit",
        "1",
        "--batch",
        "trial",
        "--results",
        "trial.json",
    ]
    assert made.stdout.startswith("Partial run, not the protocol's figures.")
    assert not PAGE.exists()
    assert not RESULTS.exists()
    assert (world / "runs" / "pcb4" / "trial" / "run.json").is_file()


def test_a_trial_run_writes_a_page_where_it_is_told_to(world: Path) -> None:
    """With --readme the page is written, marked partial."""
    with FakeVlm(REPLIES[:1]) as server:
        result = _bench(server, "--part", "pcb1", "--results", "trial.json", "--readme", "trial.md")
    assert result.exit_code == 0, result.output
    assert "**This is a partial run**" in Path("trial.md").read_text(encoding="utf-8")


def test_a_run_against_another_setting_is_not_called_a_repeat(world: Path) -> None:
    """An earlier record of another making is replaced, and the reason for no comparison said."""
    with FakeVlm([*REPLIES, *REPLIES]) as server:
        assert _bench(server).exit_code == 0
        first = read_record(RESULTS)
        judge = first.judge.model_copy(update={"image_min_tokens": "1024"})
        write_record(RESULTS, first.model_copy(update={"judge": judge}))
        second = _bench(server)

    assert second.exit_code == 0, second.output
    assert read_record(RESULTS).repeat is None
    assert "the image token minimum" in second.stderr


def test_the_page_is_written_again_from_the_record_without_running_anything(world: Path) -> None:
    """--render-only reads the figures and rewrites the page; the other setting stands beside."""
    with FakeVlm(REPLIES) as server:
        assert _bench(server).exit_code == 0
        shutil.copy(RESULTS, RESULTS.with_name("bench-own-image-tokens.json"))
        PAGE.unlink()
        asked = len(server.requests)
        result = _bench(server, "--render-only")
        assert len(server.requests) == asked

    assert result.exit_code == 0, result.output
    assert "## The other image setting" in PAGE.read_text(encoding="utf-8")
    assert result.stdout.splitlines()[-1] == f"Page: {PAGE}"


def test_render_only_without_a_record_says_so(world: Path) -> None:
    """There is nothing to render before the first run."""
    with FakeVlm() as server:
        result = _bench(server, "--render-only")
    assert result.exit_code == 1
    assert "results/stage1/bench.json" in result.output


def test_a_server_that_is_down_fails_the_verb_and_writes_nothing(world: Path) -> None:
    """Exit 1, the way to start the server, and no figures file."""
    result = runner.invoke(
        app, ["bench"], env={"SPEC_TO_INSPECTOR_VLM_URL": "http://127.0.0.1:9/v1"}
    )

    assert result.exit_code == 1
    assert "scripts/serve_vlm.sh start" in result.output
    assert not RESULTS.exists()


def test_a_run_voided_mid_way_leaves_the_earlier_figures_as_they_were(world: Path) -> None:
    """The server lost after two answers: exit 1, and the tracked file is not touched."""
    with FakeVlm(REPLIES) as server:
        assert _bench(server).exit_code == 0
    before = RESULTS.read_bytes()
    with FakeVlm(REPLIES[:2]) as server:
        result = _bench(server)

    assert result.exit_code == 1
    assert "void" in result.output
    assert RESULTS.read_bytes() == before


def test_a_part_the_labelled_set_does_not_cover_is_a_usage_error(world: Path) -> None:
    """pcb2 has an anomaly model but no clause, so it has no row to score against."""
    with FakeVlm() as server:
        result = _bench(server, "--part", "pcb2")
    assert result.exit_code == 2
    assert "pcb1, pcb4" in result.output
