"""Tests for the bench's run: the whole pipeline against a stub model and a fake judge."""

import hashlib
import json
import stat
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, cast

import pytest
import torch

from spec_to_inspector.anomaly.records import RunIndex
from spec_to_inspector.bench import run as run_module
from spec_to_inspector.bench.observe import Citation
from spec_to_inspector.bench.record import BenchRecord
from spec_to_inspector.bench.run import (
    JUDGE_PROCESS_NOTE,
    OWN_MINIMUM,
    UNKNOWN,
    BenchError,
    BenchPlan,
    LoadedModel,
    ModelLoader,
    device_probes,
    image_min_tokens,
)
from spec_to_inspector.card_memory import read_xpu_memory
from spec_to_inspector.judge.answer import REASON_PATTERNS, RefusalKind
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.judge.timing import GpuReading
from spec_to_inspector.judge.vllm_server import PrefixCacheCounters
from spec_to_inspector.settings import Settings
from tests.bench.bench_fakes import (
    COLD_FLAGS,
    IMAGE_DIGEST,
    RELEASED,
    REPLIES,
    STARTED_AT,
    fake_probes,
    machine_probes,
    rate_line,
    stub_checkpoint_bytes,
    stub_models,
)
from tests.bench.conftest import ROOT, WARM_UP, run
from tests.judge.fake_vlm import FakeVlm, Reply
from tests.spec.spec_fakes import specification


def test_the_headline_counts_the_single_defect_images_and_an_unflagged_one_is_wrong(
    record: BenchRecord,
) -> None:
    """Three single-defect images: two cited right, one never flagged."""
    headline = record.scores.headline
    assert (headline.strict.all.count, headline.strict.all.n) == (2, 3)
    assert (headline.strict.by_part["pcb4"].count, headline.strict.by_part["pcb4"].n) == (1, 2)
    assert (headline.flagged.all.count, headline.on_defect.all.count) == (2, 2)
    assert headline.rows_applied == {"4.1": 1, "5.6.1": 1}
    assert record.labels.model_dump(exclude={"file"}) == {
        "images": 4,
        "single_defect": 3,
        "multi_defect": 1,
    }
    assert not record.partial


def test_the_lenient_and_per_region_figures_and_the_false_alarm_stand_apart(
    record: BenchRecord,
) -> None:
    """The multi-defect image's region 1 got no citation; the flagged good board was referred."""
    scores = record.scores
    assert (scores.lenient.all.count, scores.lenient.all.n) == (0, 1)
    assert (scores.per_region.all.count, scores.per_region.all.n) == (2, 3)
    assert scores.confusion_region["pcb4"]["dirt"] == {"no clause applies": 1}
    good = scores.good.all
    assert (good.flagged.count, good.flagged.n, good.referred.count) == (1, 3, 1)
    assert good.citations == {"5.1": 1}
    assert good.dispositions.board_review_causes == {"outside every zone": 1}
    assert scores.anomalous.area_review_causes == {"no clause applies": 1}
    assert scores.stale_region_truth == []


def test_every_image_has_a_line_and_no_correction_reached_a_prompt(
    record: BenchRecord, plan: BenchPlan
) -> None:
    """Seven images, seven decisions on disk in the bench's own run, the flag down on each."""
    assert [(o.part, o.image_id) for o in record.observations] == [
        ("pcb1", "good-0000"),
        ("pcb1", "bad-000"),
        ("pcb4", "good-0000"),
        ("pcb4", "good-0001"),
        ("pcb4", "bad-000"),
        ("pcb4", "bad-001"),
        ("pcb4", "bad-002"),
    ]
    assert record.leak.model_dump() == {"decisions": 7, "with_corrections_in_prompt": 0}
    for observation in record.observations:
        decision = load_decision(plan.runs_dir / observation.part / "bench" / observation.image_id)
        assert decision.corrected.in_prompt is False
        assert all(region.corrections == () for region in decision.regions)
    last = record.observations[-1]
    assert (last.citation, last.outcome, len(last.areas)) == (Citation.NO_CLAUSE, Outcome.REJECT, 2)
    assert last.areas[0].review_cause is Cause.NO_CLAUSE_APPLIES
    assert (plan.runs_dir / "pcb4" / "test" / "run.json").is_file()


def test_the_stages_are_timed_and_their_memory_read_for_the_process_concerned(
    record: BenchRecord,
) -> None:
    """Parse, the anomaly model per image, the judge per area; the bench's pid, the server's."""
    times = record.times
    assert times.parse_seconds == record.specification.parse_seconds >= 0
    assert (times.flagged_images, times.areas_asked) == (4, 5)
    assert times.areas_per_flagged_image == pytest.approx(1.25)
    assert times.vlm_seconds_per_area is not None
    assert times.vlm_seconds_per_area.n == 5
    assert times.flagged_image_seconds is not None
    assert times.flagged_image_seconds.n == 4
    assert set(times.anomaly_seconds_per_image) == {"pcb1", "pcb4"}
    run = record.runs["pcb4"]
    assert (run.images, run.good, run.anomalous) == (5, 2, 3)
    assert (run.flagged_good, run.flagged_anomalous) == (1, 2)
    assert run.memory.process_peak_mib == 1300
    assert record.judge_memory.process_peak_mib == 8700
    assert record.judge_memory.card_peak_mib == 10000


def test_the_judges_stage_is_read_from_the_servers_own_card_where_it_has_one(
    plan: BenchPlan,
) -> None:
    """On the B70 machine the judge has a card of its own, and its process cannot be listed."""
    probes = replace(fake_probes(), read_server_gpu=lambda _pid: GpuReading(29456, None))
    with FakeVlm(REPLIES) as server:
        record = run(plan, server, probes=probes)

    assert record.judge_memory.card_peak_mib == 29456
    assert record.judge_memory.process_peak_mib is None
    assert record.runs["pcb4"].memory.card_peak_mib == 10000
    assert record.runs["pcb4"].memory.process_peak_mib == 1300


def test_minutes_to_an_inspector_are_this_runs_parse_and_the_recorded_fit(
    record: BenchRecord,
) -> None:
    """Twelve minutes of fit a part, as its training recorded, plus the parse."""
    inspector = record.inspector
    assert inspector.fit_seconds == {"pcb1": 720.0, "pcb4": 720.0}
    parse = record.specification.parse_seconds
    assert inspector.minutes_by_part["pcb4"] == pytest.approx((parse + 720.0) / 60)
    assert inspector.minutes_all_parts == pytest.approx((parse + 1440.0) / 60)


def test_the_record_says_what_the_run_was_made_of(record: BenchRecord) -> None:
    """The protocol and the set by digest, the server by its own account and its command line."""
    assert [len(file.sha256) for file in record.protocol] == [64]
    assert record.protocol[0].path.endswith("eval/PROTOCOL.md")
    assert record.specification.equals_tracked_clause_table
    assert (record.specification.clauses, record.specification.headings) == (16, 11)
    judge = record.judge
    assert (judge.model, judge.image_min_tokens, judge.gpu) == ("fake-vlm", "1024", "Fake GPU")
    assert (judge.cache_prompt, judge.corrections, judge.max_regions) == (False, "none recalled", 3)
    assert judge.server == {"model_file": "fake-q4.gguf"}
    assert json.loads(record.model_dump_json())["schema_version"] == 2


def test_a_trial_run_takes_the_first_images_of_each_kind_and_says_it_is_partial(
    plan: BenchPlan,
) -> None:
    """With a limit of one: one good and one anomalous board a part, and a partial record."""
    limited = plan.model_copy(update={"limit": 1, "parts": ("pcb4",), "batch": "trial"})
    with FakeVlm(REPLIES[2:3]) as server:
        made = run(limited, server)
    assert [o.image_id for o in made.observations] == ["good-0000", "bad-000"]
    assert made.partial
    assert made.limit == 1
    assert made.labels.images == 1
    assert (plan.runs_dir / "pcb4" / "trial" / "bad-000" / "decision.json").is_file()


def test_a_server_that_does_not_answer_stops_the_run_before_anything_is_scored(
    plan: BenchPlan,
) -> None:
    """The check comes first: no run directory is made for nothing."""
    with FakeVlm() as server, pytest.raises(BenchError, match=r"serve_vlm\.sh start"):
        run(plan, server, probes=fake_probes(up=False))
    assert not (plan.runs_dir / "pcb1" / "bench").exists()


def test_a_server_lost_mid_run_voids_therun(plan: BenchPlan) -> None:
    """A figure with unasked areas in it would be another figure: nothing is returned."""
    with FakeVlm(REPLIES[:2]) as server, pytest.raises(BenchError, match="void"):
        run(plan, server)


def test_a_parse_that_is_not_the_tracked_clause_table_stops_therun(plan: BenchPlan) -> None:
    """The judge is given the table the parser gives, so the two must be one."""
    with FakeVlm() as server, pytest.raises(BenchError, match="does not give the tracked"):
        run(plan, server, parse=lambda _pdf: specification())


def test_region_columns_that_are_not_this_models_stop_therun(plan: BenchPlan) -> None:
    """A labelled set built from another model's regions is named, with the way to rebuild it."""
    text = plan.labels.read_text(encoding="utf-8")
    plan.labels.write_text(
        text.replace(
            "scratch,single,5.6,one type,scratch,5.6",
            "scratch,single,5.6,off the labelled defect,,",
        ),
        encoding="utf-8",
    )
    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="pcb4 bad-000") as raised:
        run(plan, server)
    assert "bench.labels --run bench" in str(raised.value)


def _stale_on_both_parts(plan: BenchPlan) -> None:
    """Make the labelled set disagree with the stub's regions on a board of each part.

    Args:
        plan: The plan, whose labelled set is rewritten.
    """
    text = plan.labels.read_text(encoding="utf-8")
    for row in ("melt,single,4.1,one type,melt,4.1", "scratch,single,5.6,one type,scratch,5.6"):
        assert row in text
        text = text.replace(row, f"{row.rsplit(',one type', 1)[0]},off the labelled defect,,")
    plan.labels.write_text(text, encoding="utf-8")


def test_a_whole_run_names_every_stale_board_of_every_part_before_it_asks_the_judge(
    plan: BenchPlan,
) -> None:
    """Both parts are scored first, so one run gives both the names and both run directories."""
    _stale_on_both_parts(plan)

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError) as raised:
        run(plan, server)

    assert "pcb1 bad-000" in str(raised.value)
    assert "pcb4 bad-000" in str(raised.value)
    assert "bench.labels --run bench" in str(raised.value)
    assert server.requests == []
    assert (plan.runs_dir / "pcb1" / "bench" / "run.json").is_file()
    assert (plan.runs_dir / "pcb4" / "bench" / "run.json").is_file()


def test_a_whole_part_is_still_held_to_the_columns(plan: BenchPlan) -> None:
    """One part with no limit batches as the whole set does, so it stops as a whole run does."""
    _stale_on_both_parts(plan)
    one_part = plan.model_copy(update={"parts": ("pcb1",)})

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="pcb1 bad-000"):
        run(one_part, server)


def test_a_limited_trial_names_a_stale_board_and_goes_on(plan: BenchPlan) -> None:
    """Its batches are not the whole split's, so region 1 may differ there for no fault of the set.

    The record pane measured `bad-029` on both sides of its threshold between a trial of 30 and the
    whole part: a trial that stopped on that would say nothing of the columns.
    """
    _stale_on_both_parts(plan)
    trial = plan.model_copy(update={"limit": 1, "parts": ("pcb1",)})
    said: list[str] = []

    with FakeVlm(default=REPLIES[0]) as server:
        record = run(trial, server, say=said.append)

    assert record.partial
    assert record.scores.stale_region_truth == ["pcb1 bad-000"]
    assert any("pcb1 bad-000" in line and "whole split" in line for line in said)


def _digests_naming(path: Path, part: str, sha256: str) -> None:
    """Rewrite a record of the checkpoints so that it names another digest for a part.

    Args:
        path: The record.
        part: The part.
        sha256: The digest it should name.
    """
    written = json.loads(path.read_text(encoding="utf-8"))
    written["named"][part]["sha256"] = sha256
    path.write_text(json.dumps(written), encoding="utf-8")


def test_a_stage_two_run_holds_each_checkpoint_to_the_digest_on_record(
    stage2_record: BenchRecord, stage2_plan: BenchPlan
) -> None:
    """The record says which file it was held to, by its digest, and lacks nothing for that."""
    assert stage2_plan.checkpoints is not None
    held = stage2_record.checkpoints_held_to
    assert held is not None
    assert (held.path, held.sha256) == (
        stage2_plan.checkpoints.as_posix(),
        _digest(stage2_plan.checkpoints),
    )
    assert not any("held" in reason for reason in stage2_record.not_final)


def test_a_checkpoint_that_is_not_the_named_one_voids_the_run(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """The void rule's last clause: nothing scored, nothing asked, no record, the model let go."""
    assert stage2_plan.checkpoints is not None
    _digests_naming(stage2_plan.checkpoints, "pcb1", "0" * 64)
    RELEASED.clear()

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError) as raised:
        run(stage2_plan, server, probes=machine_probes(), models=machine_models)

    message = str(raised.value)
    assert "void" in message
    assert "0" * 64 in message
    assert "pcb1" in message
    assert server.requests == []
    assert not (stage2_plan.runs_dir / "pcb1" / "bench").exists()
    assert RELEASED == ["pcb1"]


def test_the_second_parts_checkpoint_voids_the_run_as_well(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """The first part passing says nothing of the second; the judge is not reached either way."""
    assert stage2_plan.checkpoints is not None
    _digests_naming(stage2_plan.checkpoints, "pcb4", "1" * 64)

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="pcb4"):
        run(stage2_plan, server, probes=machine_probes(), models=machine_models)

    assert server.requests == []


def test_the_digest_is_of_the_file_as_it_stands_when_the_model_is_loaded(
    stage2_plan: BenchPlan, tmp_path: Path
) -> None:
    """Bytes changed on disk are another checkpoint, whatever its name and size."""

    def tampered(part: str) -> LoadedModel:
        checkpoint = tmp_path / "models" / part / "model.ckpt"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_bytes(stub_checkpoint_bytes(part)[::-1])
        return stub_models(part)._replace(checkpoint=checkpoint)

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="void"):
        run(stage2_plan, server, probes=machine_probes(), models=tampered)


def test_a_stage_two_model_with_no_file_voids_the_run(stage2_plan: BenchPlan) -> None:
    """No digest to compare is no pass."""
    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="no file"):
        run(stage2_plan, server, probes=machine_probes(), models=stub_models)


@pytest.mark.parametrize("absent", [True, False])
def test_a_stage_two_run_with_no_record_of_the_digests_stops_before_it_starts(
    stage2_plan: BenchPlan, machine_models: ModelLoader, tmp_path: Path, absent: bool
) -> None:
    """Named nowhere or named and missing: nothing is parsed, scored or asked."""
    update = {"checkpoints": None if absent else tmp_path / "nowhere.json"}
    plan = stage2_plan.model_copy(update=update)

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="digests"):
        run(plan, server, probes=machine_probes(), models=machine_models)

    assert server.requests == []
    assert not (plan.runs_dir / "pcb1" / "bench").exists()


def test_stage_one_is_held_to_no_digest(record: BenchRecord) -> None:
    """The laptop's run and its record are as they were."""
    assert record.checkpoints_held_to is None
    assert record.not_final == []


def test_a_partial_trial_on_the_machine_is_held_to_the_digests_too(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """A trial on the wrong checkpoint would show nothing of the right one."""
    assert stage2_plan.checkpoints is not None
    _digests_naming(stage2_plan.checkpoints, "pcb1", "2" * 64)
    trial = stage2_plan.model_copy(update={"limit": 1})

    with FakeVlm(REPLIES) as server, pytest.raises(BenchError, match="void"):
        run(trial, server, probes=machine_probes(), models=machine_models)


def test_the_image_token_minimum_is_read_from_the_servers_command_line() -> None:
    """The flag's value, the model's own minimum without the flag, unknown without a command."""
    assert image_min_tokens(("llama-server", "--image-min-tokens", "1024")) == "1024"
    assert image_min_tokens(("llama-server", "--image-min-tokens=256")) == "256"
    assert image_min_tokens(("llama-server", "--jinja")) == OWN_MINIMUM
    assert image_min_tokens(None) == UNKNOWN


def test_each_parts_model_is_released_before_the_judge_is_asked(plan: BenchPlan) -> None:
    """The judge's stage finds the card without the anomaly model on it."""
    RELEASED.clear()
    asked_when_released: list[int] = []
    with FakeVlm(REPLIES) as server:

        def models(part: str) -> LoadedModel:
            loaded = stub_models(part)

            def release() -> None:
                asked_when_released.append(len(server.requests))
                loaded.release()

            return loaded._replace(release=release)

        run(plan, server, models=models)

    assert RELEASED == ["pcb1", "pcb4"]
    assert asked_when_released == [0, 0]


def test_a_model_is_released_even_when_scoring_fails(plan: BenchPlan) -> None:
    """An error in the anomaly model's stage does not leave the model on the card."""
    RELEASED.clear()

    def failing(*_arguments: object) -> RunIndex:
        message = "CUDA out of memory"
        raise RuntimeError(message)

    with FakeVlm() as server, pytest.raises(BenchError, match="CUDA out of memory"):
        run(plan, server, scoring=failing)
    assert RELEASED == ["pcb1"]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_figure_9s_memory_is_read_from_xpu_smi_through_the_reader(
    stage2_plan: BenchPlan, machine_models: ModelLoader, tmp_path: Path
) -> None:
    """A stand-in printing what `xpu-smi` printed: the judge's process is null and says why."""
    program = tmp_path / "fake-xpu-smi"
    program.write_text(
        '#!/bin/sh\ncase "$1" in ps) echo \'{"device_util_by_proc_list": []}\' ;; '
        "*) echo 29455.73 ;; esac\n",
        encoding="utf-8",
    )
    program.chmod(program.stat().st_mode | stat.S_IXUSR)
    read = partial(read_xpu_memory, program=str(program))
    probes = replace(machine_probes(), read_gpu=read, read_server_gpu=read)

    with FakeVlm([WARM_UP, *REPLIES]) as server:
        record = run(stage2_plan, server, probes=probes, models=machine_models)

    memory = record.judge_memory
    assert (memory.card_peak_mib, memory.card_before_mib) == (29456, 29456)
    assert memory.process_peak_mib is None
    assert memory.process_note == JUDGE_PROCESS_NOTE
    assert (memory.source, memory.card) == ("xpu-smi", "0000:ba:00.0")
    assert record.runs["pcb4"].memory.card_peak_mib == 29456
    assert record.runs["pcb4"].memory.source == "xpu-smi"
    assert memory.samples >= 1
    assert memory.interval_seconds == pytest.approx(0.01)


def test_a_process_that_is_read_needs_no_note(stage2_record: BenchRecord) -> None:
    """The bench's own process is listed on its card, so its figure stands with no note."""
    memory = stage2_record.runs["pcb1"].memory
    assert (memory.process_peak_mib, memory.card_peak_mib) == (1300, 1860)
    assert memory.process_note is None
    assert memory.card == "0, under ZE_AFFINITY_MASK=0"


def test_the_protocols_files_in_force_are_listed_with_their_digests(
    stage2_record: BenchRecord,
) -> None:
    """The protocol first, then its dated additions by name, each by its bytes at the run."""
    eval_dir = ROOT / "eval"
    protocol = eval_dir / "PROTOCOL-stage2.md"
    in_force = [protocol, *sorted(eval_dir.glob("PROTOCOL-stage2-addition-*.md"))]

    assert [(file.path, file.sha256) for file in stage2_record.protocol] == [
        (path.as_posix(), _digest(path)) for path in in_force
    ]
    named = {path.name for path in in_force}
    assert "PROTOCOL-stage2-addition-region-columns-2026-11-07.md" in named
    assert "PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md" in named
    assert not any(file.path.endswith("eval/PROTOCOL.md") for file in stage2_record.protocol)


def test_stage_ones_protocol_is_not_given_stage_twos_additions(record: BenchRecord) -> None:
    """The additions are the Stage II protocol's: Stage I's list stays a list of one."""
    assert [file.path.rpartition("/")[2] for file in record.protocol] == ["PROTOCOL.md"]


def test_a_protocol_named_in_the_configuration_is_the_one_recorded(
    stage2_plan: BenchPlan, machine_models: ModelLoader, tmp_path: Path
) -> None:
    """Any protocol can be named, and its additions are found beside it."""
    protocol = tmp_path / "protocols" / "PROTOCOL-next.md"
    protocol.parent.mkdir()
    protocol.write_text("the next protocol\n", encoding="utf-8")
    addition = protocol.with_name("PROTOCOL-next-addition-a-2026-12-01.md")
    addition.write_text("its addition\n", encoding="utf-8")
    protocol.with_name("PROTOCOL-next-notes.md").write_text("no addition\n", encoding="utf-8")

    with FakeVlm([WARM_UP, *REPLIES]) as server:
        record = run(
            stage2_plan.model_copy(update={"protocol": protocol}),
            server,
            probes=machine_probes(),
            models=machine_models,
        )

    assert [file.path for file in record.protocol] == [protocol.as_posix(), addition.as_posix()]
    assert protocol.as_posix() in record.notes["protocol"]
    assert addition.as_posix() in record.notes["protocol"]


def test_which_server_answered_is_in_the_record_with_where_each_fact_came_from(
    stage2_record: BenchRecord,
) -> None:
    """Week 1's `judge.server` was empty, its minimum `unknown` and its card null."""
    judge = stage2_record.judge

    assert judge.server["image"] == "intel/llm-scaler-vllm:0.26.0-b1"
    assert judge.server["image_digest"] == IMAGE_DIGEST
    assert judge.server["vllm_version"].startswith("0.26.1.dev0")
    assert judge.server["dtype"] == "float16"
    assert judge.server_sources["vllm_version"] == "GET /version"
    assert judge.image_min_tokens == "1024"
    assert judge.gpu == "Intel(R) Arc(TM) Pro B70 Graphics"


def test_the_cold_is_read_from_the_servers_start_and_its_log_is_kept(
    stage2_record: BenchRecord, stage2_plan: BenchPlan
) -> None:
    """The flags, the engine's own word, the rate in the log, and that log beside the record."""
    cold = stage2_record.judge.cold

    assert cold is not None
    assert cold.server_flags == COLD_FLAGS
    assert cold.engine_prefix_caching is False
    assert cold.server_started_at == STARTED_AT
    assert (cold.prefix_cache_hits, cold.prefix_cache_queries) == (0, 0)
    assert (cold.hit_rate_percent, cold.hit_rate_readings) == (0.0, 2)
    assert stage2_plan.server_log is not None
    assert stage2_plan.server_log.read_text(encoding="utf-8") == rate_line("0.0") * 2
    assert cold.server_log is not None
    assert cold.server_log.sha256 == _digest(stage2_plan.server_log)
    assert "the server's start" in stage2_record.notes["cold"]


@pytest.mark.parametrize(
    ("log", "counters"),
    [
        pytest.param(
            rate_line("0.0") + rate_line("92.4"),
            (PrefixCacheCounters(0, 0), PrefixCacheCounters(0, 0)),
            id="in the log",
        ),
        pytest.param(
            rate_line("0.0"),
            (PrefixCacheCounters(100, 500), PrefixCacheCounters(101, 900)),
            id="in the counters",
        ),
    ],
)
def test_a_prefix_cache_hit_voids_the_run_and_keeps_the_log_that_says_so(
    stage2_plan: BenchPlan,
    machine_models: ModelLoader,
    log: str,
    counters: tuple[PrefixCacheCounters, PrefixCacheCounters],
) -> None:
    """The protocol's void rule: any rate above 0.0% and no figures are reported."""
    with (
        FakeVlm([WARM_UP, *REPLIES]) as server,
        pytest.raises(BenchError, match="void") as raised,
    ):
        run(
            stage2_plan,
            server,
            probes=machine_probes(log=log, counters=counters),
            models=machine_models,
        )

    assert "serve_vlm_xpu.sh" in str(raised.value)
    assert stage2_plan.server_log is not None
    assert stage2_plan.server_log.read_text(encoding="utf-8") == log


def test_counters_that_started_above_zero_do_not_void_a_run_that_added_nothing(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """What the server counted before the run is not this run's."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        record = run(
            stage2_plan,
            server,
            probes=machine_probes(counters=(PrefixCacheCounters(7, 9), PrefixCacheCounters(7, 9))),
            models=machine_models,
        )
    assert record.judge.cold is not None
    assert record.judge.cold.prefix_cache_hits == 0


def test_a_hit_rate_that_could_not_be_read_is_not_written_as_zero(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """Unread is null, and the record says the run cannot be final for it."""
    probes = machine_probes(log="", counters=(None, None))
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        record = run(stage2_plan, server, probes=probes, models=machine_models)

    cold = record.judge.cold
    assert cold is not None
    assert cold.hit_rate_percent is None
    assert cold.prefix_cache_hits is None
    assert any("hit rate" in reason for reason in record.not_final)


def test_each_checkpoint_is_named_by_its_digest(stage2_record: BenchRecord, tmp_path: Path) -> None:
    """The void rule needs the checkpoint's SHA-256, read from the file that was loaded."""
    for part in ("pcb1", "pcb4"):
        path = tmp_path / "models" / part / "model.ckpt"
        checkpoint = stage2_record.runs[part].checkpoint
        assert checkpoint is not None
        assert (checkpoint.path, checkpoint.sha256) == (path.as_posix(), _digest(path))


def test_the_warm_up_is_asked_once_before_the_clock_and_its_answer_goes_nowhere(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """One more request than the run's, first, about the first flagged board; only that it was."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        record = run(stage2_plan, server, probes=machine_probes(), models=machine_models)
        assert len(server.requests) == len(REPLIES) + 1
        assert server.requests[0]["messages"] == server.requests[1]["messages"]

    warm_up = record.judge.warm_up
    assert warm_up is not None
    assert (warm_up.asked, warm_up.image) == (True, "pcb1 bad-000")
    assert warm_up.seconds is not None
    assert "asked only to warm" not in record.model_dump_json()
    first = load_decision(stage2_plan.runs_dir / "pcb1" / "bench" / "bad-000")
    assert first.regions[0].answer is not None
    assert "asked only to warm" not in first.model_dump_json()
    assert record.times.areas_asked == 5


def test_stage_one_asks_no_warm_up(record: BenchRecord) -> None:
    """Stage I's protocol has none: `record`'s fixture counts its requests."""
    assert record.judge.warm_up is None
    assert record.judge.cold is None


def test_a_server_that_cannot_answer_the_warm_up_stops_the_run(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """The warm-up is the run's first question, and it says which script to start."""
    with FakeVlm() as server, pytest.raises(BenchError, match="warm-up") as raised:
        run(stage2_plan, server, probes=machine_probes(), models=machine_models)
    assert "scripts/serve_vlm_xpu.sh start" in str(raised.value)


def test_a_run_that_flags_nothing_says_the_warm_up_was_not_asked(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """With nothing flagged there is nothing to ask about, and the record does not pretend."""
    plan = stage2_plan.model_copy(update={"limit": 1, "parts": ("pcb1",), "batch": "calm"})

    def calm(part: str) -> LoadedModel:
        loaded = machine_models(part)
        scorer = cast("Any", loaded.scorer)
        scorer.score = lambda images: (
            torch.full((len(images),), 10.0),
            torch.full((len(images), 256, 256), 5.0),
        )
        return loaded

    text = stage2_plan.labels.read_text(encoding="utf-8")
    plan.labels.write_text(
        text.replace("melt,single,4.1,one type,melt,4.1", "melt,single,4.1,no region,,"),
        encoding="utf-8",
    )
    with FakeVlm() as server:
        record = run(plan, server, probes=machine_probes(), models=calm)
        assert server.requests == []

    assert record.judge.warm_up is not None
    assert not record.judge.warm_up.asked
    assert "the warm-up having been asked" in record.not_final


def test_the_boards_on_the_threshold_are_named_with_their_scores(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """The stub's speck scores 45: at a threshold of 45 it is on it, and a strict `>` leaves it."""

    def on_it(part: str) -> LoadedModel:
        loaded = machine_models(part)
        scorer = cast("Any", loaded.scorer)
        scorer.thresholds = scorer.thresholds.model_copy(update={"image": 45.0})
        return loaded

    with FakeVlm(default=REPLIES[0]) as server:
        record = run(stage2_plan, server, probes=machine_probes(), models=on_it)

    found = record.on_threshold
    assert found is not None
    assert found.parts == ("pcb1", "pcb4")
    assert found.tolerance == pytest.approx(1e-3)
    assert [(b.part, b.image_id, b.label, b.score, b.threshold, b.above) for b in found.boards] == [
        ("pcb4", "good-0001", "good", 45.0, 45.0, False)
    ]


def test_a_run_with_no_board_on_the_threshold_says_there_is_none(
    stage2_record: BenchRecord,
) -> None:
    """Empty, with the parts it looked at: not silence."""
    assert stage2_record.on_threshold is not None
    assert stage2_record.on_threshold.boards == ()
    assert stage2_record.on_threshold.parts == ("pcb1", "pcb4")


def test_the_final_setting_lists_no_digit_reasons_and_says_its_pattern(
    stage2_record: BenchRecord,
) -> None:
    """The listing is the comparison's: the final setting's record has its pattern and no list."""
    assert stage2_record.digit_reasons is None
    assert stage2_record.judge.reason_pattern == REASON_PATTERNS["no_digits"]


def test_the_designators_comparison_lists_every_reason_with_a_digit(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """Listed by board, a size counted where one got through, and the schema sent is its own."""
    designator = json.dumps(
        {"reason": "a lump of solder on R12", "defect_class": "melt", "clause_id": "4.1"}
    )
    size = json.dumps(
        {"reason": "a scratch of R5 mm", "defect_class": "scratch", "clause_id": "5.6"}
    )
    replies = [WARM_UP, designator, REPLIES[1], size, *REPLIES[3:]]
    plan = stage2_plan.model_copy(update={"reason_rule": "designators"})

    with FakeVlm(replies) as server:
        record = run(plan, server, probes=machine_probes(), models=machine_models)
        sent = server.requests[-1]["response_format"]["json_schema"]["schema"]

    assert sent["properties"]["reason"]["pattern"] == REASON_PATTERNS["designators"]
    assert record.judge.reason_pattern == REASON_PATTERNS["designators"]
    listed = record.digit_reasons
    assert listed is not None
    assert [
        (r.part, r.image_id, r.reason, r.valid, r.followed_by_a_unit) for r in listed.reasons
    ] == [
        ("pcb1", "bad-000", "a lump of solder on R12", True, False),
        ("pcb4", "bad-000", "a scratch of R5 mm", True, True),
    ]
    assert listed.followed_by_a_unit == 1
    assert any("designators" in reason for reason in record.not_final)


def test_a_refused_padded_answer_is_counted_under_its_own_heading(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """The addition: it runs to the token limit, is refused as not JSON, and the record says so."""
    padded = Reply('{"reason": "' + "a mark " * 40, finish_reason="length")
    replies = [WARM_UP, padded, *REPLIES]
    plan = stage2_plan.model_copy(update={"reason_rule": "designators"})

    with FakeVlm(replies) as server:
        record = run(plan, server, probes=machine_probes(), models=machine_models)

    refused = record.refused_answers
    assert refused is not None
    assert refused.padded == 1
    assert refused.by_kind["padded to the token limit"] == 1
    assert [(r.part, r.image_id, r.area, r.attempt, r.kind) for r in refused.answers] == [
        ("pcb1", "bad-000", 1, 1, RefusalKind.PADDED)
    ]


def test_stage_two_counts_refusals_under_every_rule_and_stage_one_does_not(
    stage2_record: BenchRecord, record: BenchRecord
) -> None:
    """The final setting has padded answers too; Stage I's record stays as it was."""
    assert stage2_record.refused_answers is not None
    assert stage2_record.refused_answers.answers == ()
    assert record.refused_answers is None


def test_a_stage_two_run_with_everything_read_lacks_nothing_for_a_final(
    stage2_record: BenchRecord,
) -> None:
    """All that a partial run on the small set can lack is the set itself: this one is whole."""
    assert stage2_record.stage == "II"
    assert stage2_record.unit == "stage2"
    assert stage2_record.not_final == []


def test_the_machines_messages_name_the_machines_script_and_python(
    stage2_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """Never `scripts/serve_vlm.sh` or a bare `uv run` where the run is on the machine."""
    probes = replace(machine_probes(), reachable=lambda _url: False)
    with FakeVlm() as server, pytest.raises(BenchError, match=r"serve_vlm_xpu\.sh start"):
        run(stage2_plan, server, probes=probes, models=machine_models)
    assert stage2_plan.python == ".venv/bin/python"


def test_the_devices_probes_read_the_machine_on_an_intel_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On `xpu` the server is read from its container, and each stage's card is named."""
    monkeypatch.setenv("ZE_AFFINITY_MASK", "0")
    monkeypatch.setattr(run_module, "read_xpu_address", lambda: "0000:17:00.0")
    probes = device_probes(Settings(device="xpu", vlm_card="0000:ba:00.0"))

    assert probes.memory_source == "xpu-smi"
    assert probes.judge_card == "0000:ba:00.0"
    assert probes.anomaly_card == "0000:17:00.0, under ZE_AFFINITY_MASK=0"
    assert probes.server is not None
    assert probes.server.settle_seconds > 10.0
    monkeypatch.setattr(run_module, "read_xpu_address", lambda: None)
    assert device_probes(Settings(device="xpu")).anomaly_card == (
        "the first visible, under ZE_AFFINITY_MASK=0"
    )
    assert device_probes(Settings(device="cuda")).server is None
    assert device_probes(Settings(device="cuda")).memory_source == "nvidia-smi"
