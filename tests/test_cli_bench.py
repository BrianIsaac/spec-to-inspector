"""Tests for the `bench` verb, against a stub anomaly model and a fake VLM server."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from spec_to_inspector import cli
from spec_to_inspector.anomaly.infer import visa_test_items
from spec_to_inspector.bench import run as benching
from spec_to_inspector.bench.paired import read_paired
from spec_to_inspector.bench.record import read_record, write_record
from spec_to_inspector.cli import app
from spec_to_inspector.judge.answer import REASON_PATTERNS
from spec_to_inspector.settings import Settings
from tests.bench.bench_fakes import (
    REPLIES,
    machine_probes,
    stub_models,
    stub_models_with_files,
    stub_scoring,
    write_bench_labels,
    write_bench_visa,
    write_checkpoint_record,
)
from tests.bench.conftest import WARM_UP, tracked
from tests.judge.fake_vlm import FakeVlm

ROOT = Path(__file__).parents[1]
RESULTS = Path("results/stage1/bench.json")
PAGE = Path("results/stage1/README.md")
DIGESTS = Path("results/stage2/checkpoints.json")

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
    for protocol in (ROOT / "eval").glob("PROTOCOL*.md"):
        shutil.copy(protocol, Path("eval") / protocol.name)
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
    assert [file.path for file in record.protocol] == ["eval/PROTOCOL.md"]
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


@pytest.fixture
def machine(world: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put the verb on the machine: an Intel card, its server in a container.

    Returns:
        The working directory.
    """
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DEVICE", "xpu")
    monkeypatch.setattr(benching, "device_probes", lambda _settings: machine_probes())
    write_checkpoint_record(DIGESTS)

    def pipeline(_settings: Settings) -> benching.Pipeline:
        return benching.Pipeline(
            parse=tracked,
            models=stub_models_with_files(world / "models"),
            test_items=visa_test_items,
            scoring=stub_scoring,
        )

    monkeypatch.setattr(benching, "laptop_pipeline", pipeline)
    return world


def test_on_the_machine_the_verb_follows_stage_twos_protocol_and_writes_its_own_page(
    machine: Path,
) -> None:
    """The protocol's command: its record, its page and the server's log, under `final/`."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        result = _bench(server, "--results", "final/bench.json", "--readme", "final/README.md")

    assert result.exit_code == 0, result.output
    record = read_record(Path("final/bench.json"))
    assert record.stage == "II"
    assert [file.path for file in record.protocol] == [
        "eval/PROTOCOL-stage2.md",
        "eval/PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md",
        "eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md",
    ]
    assert Path("final/README.md").read_text(encoding="utf-8").startswith("# Stage II:")
    logs = list(Path("final").glob("bench.server-log.*.txt"))
    assert len(logs) == 1
    assert record.judge.cold is not None
    assert record.judge.cold.server_log is not None
    assert record.judge.cold.server_log.path == logs[0].as_posix()
    assert not RESULTS.exists()


def test_on_the_machine_stage_ones_default_paths_are_refused(machine: Path) -> None:
    """The protocol's own cold check: a run there must never replace `results/stage1/`."""
    with FakeVlm() as server:
        result = _bench(server)
        assert server.requests == []
    assert result.exit_code == 2
    assert "--results" in result.output
    assert not RESULTS.exists()


def test_on_the_machine_a_comparison_does_not_go_beside_the_run(machine: Path) -> None:
    """The protocol gives each comparison files of its own."""
    with FakeVlm() as server:
        result = _bench(server, "--results", "r.json", "--beside", "other.json")
    assert result.exit_code == 2
    assert "--beside" in result.output


def test_a_protocol_named_in_the_configuration_is_followed(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SPEC_TO_INSPECTOR_PROTOCOL_FILE` names the file, whatever the stage's default."""
    Path("other.md").write_text("another protocol\n", encoding="utf-8")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_PROTOCOL_FILE", "other.md")
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        result = _bench(server, "--results", "r.json")
    assert result.exit_code == 0, result.output
    assert [file.path for file in read_record(Path("r.json")).protocol] == ["other.md"]


def test_the_comparisons_rule_is_taken_from_the_configuration(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pattern is the client's: one setting, the same command, and it says it is no final."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_REASON_RULE", "designators")
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        result = _bench(server, "--results", "r.json", "--readme", "r.md")
        pattern = server.requests[0]["response_format"]["json_schema"]["schema"]["properties"][
            "reason"
        ]["pattern"]

    assert result.exit_code == 0, result.output
    assert pattern == REASON_PATTERNS["designators"]
    assert read_record(Path("r.json")).digit_reasons is not None
    assert "Not yet final: the final setting" in result.stdout
    assert "## The reasons with a digit in them" in Path("r.md").read_text(encoding="utf-8")


def test_on_the_laptop_nothing_of_the_machines_is_written(world: Path) -> None:
    """Stage I's protocol, no warm-up, no log, and its own page."""
    with FakeVlm(REPLIES) as server:
        assert _bench(server).exit_code == 0

    record = read_record(RESULTS)
    assert record.stage == "I"
    assert record.judge.warm_up is None
    assert list(RESULTS.parent.glob("*server-log*")) == []
    assert PAGE.read_text(encoding="utf-8").startswith("# Stage I: what the laptop prototype")


def _a_pair_of_runs(server: FakeVlm) -> None:
    """Run the protocol's command twice into a final folder and once into a comparison's.

    Args:
        server: The fake judge, with replies for all three.
    """
    for folder in ("final", "comparison-fp8", "comparison-fp8"):
        result = _bench(
            server, "--results", f"{folder}/bench.json", "--readme", f"{folder}/README.md"
        )
        assert result.exit_code == 0, result.output


def test_on_the_machine_a_comparison_is_paired_with_the_final_from_the_two_records(
    machine: Path,
) -> None:
    """Figure 10 needs no run: two records, the labelled set, a file and the page beside them."""
    with FakeVlm([*[WARM_UP, *REPLIES] * 3]) as server:
        _a_pair_of_runs(server)
        asked = len(server.requests)
        result = _bench(
            server,
            "--render-only",
            "--against",
            "final/bench.json",
            "--results",
            "comparison-fp8/bench.json",
            "--readme",
            "comparison-fp8/README.md",
        )
        assert len(server.requests) == asked

    assert result.exit_code == 0, result.output
    paired = read_paired(Path("comparison-fp8/paired.json"))
    assert paired.final.path == "final/bench.json"
    assert paired.comparison_is_a_repeat
    assert (paired.strict.boards, paired.lenient.boards) == (3, 1)
    assert paired.strict.sign_test.p_value == 1.0
    page = Path("comparison-fp8/README.md").read_text(encoding="utf-8")
    assert "## 10. The paired table, against the final run" in page
    assert "| Strict, single-defect | 3 | 2 | 1 | 0 | 0 | 0 | 1 | no |" in page


def test_a_comparison_run_with_against_writes_the_figure_as_it_ends(machine: Path) -> None:
    """The same in one command, on the run itself, named for the first run it is."""
    with FakeVlm([*[WARM_UP, *REPLIES] * 2]) as server:
        first = _bench(server, "--results", "final/bench.json", "--readme", "final/README.md")
        second = _bench(
            server,
            "--against",
            "final/bench.json",
            "--results",
            "comparison-fp8/bench.json",
            "--readme",
            "comparison-fp8/README.md",
        )

    assert first.exit_code == second.exit_code == 0, second.output
    assert not read_paired(Path("comparison-fp8/paired.json")).comparison_is_a_repeat
    page = Path("comparison-fp8/README.md").read_text(encoding="utf-8")
    assert "the comparison's first run" in page


def test_a_page_written_again_keeps_the_figure_of_the_record_it_was_counted_from(
    machine: Path,
) -> None:
    """Rendering without --against reads the file, as long as the record is the one counted."""
    with FakeVlm([*[WARM_UP, *REPLIES] * 3]) as server:
        _a_pair_of_runs(server)
        arguments = [
            "--results",
            "comparison-fp8/bench.json",
            "--readme",
            "comparison-fp8/README.md",
        ]
        assert (
            _bench(server, "--render-only", "--against", "final/bench.json", *arguments).exit_code
            == 0
        )
        again = _bench(server, "--render-only", *arguments)

    assert again.exit_code == 0, again.output
    page = Path("comparison-fp8/README.md")
    assert "## 10. The paired table" in page.read_text(encoding="utf-8")

    record = read_record(Path("comparison-fp8/bench.json"))
    write_record(Path("comparison-fp8/bench.json"), record.model_copy(update={"measured_on": "x"}))
    with FakeVlm() as server:
        replaced = _bench(server, "--render-only", *arguments)
    assert replaced.exit_code == 0, replaced.output
    assert "## 10. The paired table" not in page.read_text(encoding="utf-8")


def test_against_needs_the_comparisons_own_record(machine: Path) -> None:
    """With no record named it would read Stage I's default path."""
    with FakeVlm() as server:
        result = _bench(server, "--render-only", "--against", "final/bench.json")
    assert result.exit_code == 2
    assert "--results" in result.output


def test_two_records_that_have_no_pairs_stop_with_the_reason(machine: Path) -> None:
    """Exit 1 and no file written: a table of nothing is worse than none."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        ran = _bench(server, "--results", "comparison-fp8/bench.json")
        assert ran.exit_code == 0, ran.output
        result = _bench(
            server,
            "--render-only",
            "--against",
            "final/missing.json",
            "--results",
            "comparison-fp8/bench.json",
        )

    assert result.exit_code == 1
    assert "missing.json" in result.output
    assert not Path("comparison-fp8/paired.json").exists()


def test_on_the_machine_the_verb_reads_the_tracked_record_of_the_digests(machine: Path) -> None:
    """By its default path, with no flag, so that the protocol's command is the one that runs."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        result = _bench(server, "--results", "final/bench.json")

    assert result.exit_code == 0, result.output
    held = read_record(Path("final/bench.json")).checkpoints_held_to
    assert held is not None
    assert held.path == DIGESTS.as_posix()


def test_on_the_machine_a_checkpoint_not_named_ends_with_exit_one_and_no_record(
    machine: Path,
) -> None:
    """The void rule as a user meets it: the reason on the screen, nothing asked or written."""
    write_checkpoint_record(DIGESTS, parts=("pcb4",))

    with FakeVlm() as server:
        result = _bench(server, "--results", "final/bench.json")
        assert server.requests == []

    assert result.exit_code == 1
    assert "pcb1" in result.output
    assert not Path("final/bench.json").exists()


def test_on_the_laptop_the_verb_needs_no_record_of_the_digests(world: Path) -> None:
    """Stage I's run is as it was."""
    assert not DIGESTS.exists()
    with FakeVlm(REPLIES) as server:
        result = _bench(server)

    assert result.exit_code == 0, result.output
    assert read_record(RESULTS).checkpoints_held_to is None
