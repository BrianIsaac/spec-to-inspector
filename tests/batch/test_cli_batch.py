"""Tests for `inspect --record`: the whole batch as a user runs it, on a stub pipeline."""

import csv
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner, Result

from spec_to_inspector import cli
from spec_to_inspector.batch.record import read_batch_record
from spec_to_inspector.batch.report import CARD_NAME, CLAUSE_TABLE_NAME, REPORT_NAME
from spec_to_inspector.bench import run as benching
from spec_to_inspector.cli import app
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.spec.pdf import ParsedPdf
from spec_to_inspector.spec.schema import read_clause_table
from tests.batch.conftest import PCB4_REPLIES
from tests.bench.bench_fakes import (
    machine_probes,
    rate_line,
    stub_scoring,
    write_checkpoint_record,
)
from tests.bench.conftest import WARM_UP, tracked
from tests.judge.fake_vlm import FakeVlm, Reply

DIGESTS = Path("results/stage2/checkpoints.json")
RECORD = Path("results/stage2/batch/pcb4.json")
PDF = "specs/pcb-spec.pdf"

runner = CliRunner()


def _inspect(server: FakeVlm, *more: str) -> Result:
    return runner.invoke(
        app,
        ["inspect", "-c", "pcb4", "--spec", PDF, "--test-split", "--batch", "batch", *more],
        env={"SPEC_TO_INSPECTOR_VLM_URL": server.url},
    )


def _measured(server: FakeVlm) -> Result:
    return _inspect(server, "--record", RECORD.as_posix())


def test_one_command_goes_from_the_pdf_to_the_reject_cards(machine: Path) -> None:
    """Every board of the split judged, the cards, the report, the record, and its lines."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        result = _measured(server)
        assert all(request["cache_prompt"] is False for request in server.requests)

    assert result.exit_code == 0, result.output
    run = machine / "runs" / "pcb4" / "batch"
    record = read_batch_record(RECORD)
    assert record.part == "pcb4"
    assert record.counts.boards == 5
    assert (
        record.counts.accepted + record.counts.rejected + record.counts.referred
        == record.counts.boards
    )
    assert record.counts.rejected >= 1
    assert record.report.cards == record.counts.rejected
    assert len(list(run.glob(f"*/{CARD_NAME}"))) == record.counts.rejected
    assert (run / REPORT_NAME).is_file()
    assert [line.outcome for line in record.observations] == [
        load_decision(run / line.image_id).outcome for line in record.observations
    ]
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[-3].endswith(f"Decisions: {run}")
    assert lines[-2] == f"Report: {run / REPORT_NAME}, {record.report.cards} reject card(s)"
    assert lines[-1] == f"Figures: {RECORD}"
    assert sum(": " in line and line.split(":")[0].count("-") == 1 for line in lines[:-3]) == 5


def test_the_clause_table_is_the_one_parsed_in_the_run_and_equals_the_tracked(
    machine: Path,
) -> None:
    """The run's own table, by digest; nothing is written beside the PDF."""
    tracked_before = Path("specs/pcb-spec.clauses.json").read_bytes()
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    record = read_batch_record(RECORD)
    written = machine / "runs" / "pcb4" / "batch" / CLAUSE_TABLE_NAME
    assert record.clause_table.path == str(written)
    assert record.clause_table.sha256 == hashlib.sha256(written.read_bytes()).hexdigest()
    assert read_clause_table(written) == read_clause_table(Path("specs/pcb-spec.clauses.json"))
    assert record.specification.equals_tracked_clause_table
    assert record.specification.parse_seconds >= 0
    assert Path("specs/pcb-spec.clauses.json").read_bytes() == tracked_before


def test_the_record_holds_the_protocol_and_every_addition_by_digest(machine: Path) -> None:
    """The addition asks for its own SHA-256 beside the protocol's and the two before it."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    files = {file.path: file.sha256 for file in read_batch_record(RECORD).protocol}
    addition = Path("eval/PROTOCOL-stage2-addition-whole-batch-2026-11-07.md")
    assert files[addition.as_posix()] == hashlib.sha256(addition.read_bytes()).hexdigest()
    assert "eval/PROTOCOL-stage2.md" in files
    assert len(files) >= 4


def test_figures_seven_and_eight_are_the_benchs_own(machine: Path) -> None:
    """Time by stage after the warm-up; parse time plus the fit time recorded at training."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    record = read_batch_record(RECORD)
    times = record.times
    assert times.parse_seconds == record.specification.parse_seconds
    assert times.anomaly_seconds_per_image == {"pcb4": record.run.seconds_per_image}
    flagged = [line for line in record.observations if line.flagged]
    assert times.flagged_images == len(flagged)
    assert times.vlm_seconds_per_area is not None
    assert times.flagged_image_seconds is not None
    assert times.judge_stage_seconds > 0
    assert record.judge.warm_up is not None
    assert record.judge.warm_up.asked
    assert record.inspector.fit_seconds == {"pcb4": 720.0}
    assert record.inspector.minutes_by_part["pcb4"] == pytest.approx(
        (record.specification.parse_seconds + 720.0) / 60
    )
    assert record.report_seconds >= 0
    assert record.whole_seconds >= times.judge_stage_seconds


def test_figure_nine_is_both_cards_by_stage_with_the_readings_kept_raw(machine: Path) -> None:
    """The peaks are counted from a file of readings, each with the stage it fell in."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    record = read_batch_record(RECORD)
    memory = record.memory
    assert memory.source == "xpu-smi"
    assert memory.interval_seconds == 0.01
    assert memory.judge_card == "0000:ba:00.0"
    raw = Path(memory.readings.path)
    assert raw.parent == RECORD.parent
    assert raw.name.startswith("pcb4.cards.")
    assert memory.readings.sha256 == hashlib.sha256(raw.read_bytes()).hexdigest()
    with raw.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert memory.whole.samples == len(rows)
    stages = {row["stage"] for row in rows}
    assert stages == set(memory.by_stage)
    assert "parse" in stages
    assert "report" in stages
    assert memory.whole.anomaly_card_mib == 1860
    assert memory.whole.judge_card_mib == 29456
    assert record.run.memory.interval_seconds == 0.01
    assert record.run.memory.source == "xpu-smi"
    assert record.judge_memory.card == "0000:ba:00.0"


def test_the_servers_log_of_the_run_is_kept_beside_the_record(machine: Path) -> None:
    """As the bench keeps it, for the same void rule."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    cold = read_batch_record(RECORD).judge.cold
    assert cold is not None
    assert cold.server_log is not None
    assert Path(cold.server_log.path).name.startswith("pcb4.server-log.")
    assert Path(cold.server_log.path).is_file()
    assert cold.hit_rate_percent == 0.0


def test_two_runs_keep_their_raw_files_apart_and_the_second_replaces_the_run(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same command twice, with nothing changed: the raw files carry the moment."""
    stamps = iter(["20261107T120000Z", "20261107T121500Z"])

    class Stamp:
        @staticmethod
        def strftime(_format: str) -> str:
            return next(stamps)

    class Clock:
        @staticmethod
        def now(_zone: object) -> type[Stamp]:
            return Stamp

    monkeypatch.setattr(cli, "datetime", Clock)
    for _ in range(2):
        with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
            assert _measured(server).exit_code == 0

    assert len(list(RECORD.parent.glob("pcb4.cards.*.csv"))) == 2
    assert len(list(RECORD.parent.glob("pcb4.server-log.*.txt"))) == 2


def test_a_checkpoint_not_named_ends_it_with_exit_one_and_no_record(machine: Path) -> None:
    """The final's setting holds the checkpoints to their digests."""
    write_checkpoint_record(DIGESTS, parts=("pcb1",))
    with FakeVlm() as server:
        result = _measured(server)
        assert server.requests == []

    assert result.exit_code == 1
    assert "pcb4" in result.output
    assert not RECORD.exists()


def test_a_store_that_holds_a_correction_ends_it_before_anything_runs(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The final's setting is an empty store."""
    monkeypatch.setattr(CorrectionStore, "count", lambda _self: 2)
    with FakeVlm() as server:
        result = _measured(server)
        assert server.requests == []

    assert result.exit_code == 1
    assert "2 correction(s)" in result.output
    assert "empty store" in result.output
    assert not RECORD.exists()
    assert not (machine / "runs" / "pcb4" / "batch").exists()


def test_an_absent_store_stays_absent(machine: Path) -> None:
    """A later bench's void rule reads `runs/`: the batch must leave no store there."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    assert not (machine / "runs" / "corrections.sqlite3").exists()
    assert read_batch_record(RECORD).leak.with_corrections_in_prompt == 0


def test_a_server_not_answering_ends_it_with_exit_one_and_no_record(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is measured against nothing."""
    monkeypatch.setattr(
        benching,
        "device_probes",
        lambda _settings: machine_probes().__class__(
            **{**machine_probes().__dict__, "reachable": lambda _url: False}
        ),
    )
    with FakeVlm() as server:
        result = _measured(server)

    assert result.exit_code == 1
    assert "cannot be reached" in result.output
    assert not RECORD.exists()


def test_a_server_lost_mid_way_voids_the_run(machine: Path) -> None:
    """A board that could not be put to the judge leaves no record."""
    with FakeVlm([WARM_UP, PCB4_REPLIES[0], Reply(status=500, body="down")]) as server:
        result = _measured(server)

    assert result.exit_code == 1
    assert "void" in result.output
    assert not RECORD.exists()


def test_a_hit_in_the_servers_prefix_cache_voids_the_run_and_keeps_the_log(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same void rule as the bench's, and the log that shows it."""
    monkeypatch.setattr(
        benching, "device_probes", lambda _settings: machine_probes(log=rate_line("12.5"))
    )
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        result = _measured(server)

    assert result.exit_code == 1
    assert "prefix cache" in result.output
    assert not RECORD.exists()
    assert len(list(RECORD.parent.glob("pcb4.server-log.*.txt"))) == 1


def test_the_record_gives_no_accuracy_figure(machine: Path) -> None:
    """The addition: the final figure stands and is not re-read from a batch."""
    with FakeVlm([WARM_UP, *PCB4_REPLIES]) as server:
        assert _measured(server).exit_code == 0

    fields = cast("dict[str, object]", json.loads(RECORD.read_text(encoding="utf-8")))
    assert "scores" not in fields
    assert "labels" not in fields


@pytest.mark.parametrize(
    ("arguments", "word"),
    [
        (["--spec", "specs/pcb-spec.clauses.json", "--test-split"], "PDF"),
        (["--spec", PDF, "--run", "elsewhere"], "--test-split"),
        (["--spec", PDF, "--test-split", "--corrections"], "--corrections"),
    ],
)
def test_a_measured_run_must_be_the_whole_split_from_the_pdf(
    machine: Path, arguments: list[str], word: str
) -> None:
    """The addition names the command: the flags that would make it another run are refused."""
    (machine / "elsewhere").mkdir()
    result = runner.invoke(
        app, ["inspect", "-c", "pcb4", *arguments, "--record", RECORD.as_posix()]
    )

    assert result.exit_code == 2
    assert word in result.output
    assert not RECORD.exists()


def test_without_a_record_the_test_split_and_the_pdf_are_the_verbs_own(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A supplier's engineer needs neither a tracked table, nor a record, nor a warm-up."""

    class Parsed:
        @staticmethod
        def specification() -> object:
            return tracked(Path(PDF))

    def read_pdf(_pdf: Path, *, artifacts_dir: Path | None) -> ParsedPdf:
        assert artifacts_dir is None
        return cast("ParsedPdf", Parsed)

    monkeypatch.setattr(cli, "read_pdf", read_pdf)
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DEVICE", "cpu")
    from spec_to_inspector.anomaly import infer  # noqa: PLC0415
    from tests.bench.bench_fakes import stub_scorer  # noqa: PLC0415

    monkeypatch.setattr(
        infer.AnomalyModel, "load", lambda _root, part, *, device: stub_scorer(part)
    )
    monkeypatch.setattr(infer, "run_inference", stub_scoring)
    Path("specs/pcb-spec.clauses.json").unlink()
    with FakeVlm(PCB4_REPLIES) as server:
        result = _inspect(server, "--url", server.url)

    assert result.exit_code == 0, result.output
    run = machine / "runs" / "pcb4" / "batch"
    assert (run / CLAUSE_TABLE_NAME).is_file()
    assert (run / REPORT_NAME).is_file()
    assert read_clause_table(run / CLAUSE_TABLE_NAME) == tracked(Path(PDF))
    assert {d.name for d in run.iterdir() if d.is_dir()} == {
        "good-0000",
        "good-0001",
        "bad-000",
        "bad-001",
        "bad-002",
    }
    assert any(load_decision(run / d).outcome is Outcome.REJECT for d in ("bad-000", "bad-002"))
    assert not list(machine.glob("results/stage2/batch/*"))
