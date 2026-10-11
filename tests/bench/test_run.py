"""Tests for the bench's run: the whole pipeline against a stub model and a fake judge."""

import json

import pytest

from spec_to_inspector.anomaly.records import RunIndex
from spec_to_inspector.bench.observe import Citation
from spec_to_inspector.bench.record import BenchRecord
from spec_to_inspector.bench.run import (
    OWN_MINIMUM,
    UNKNOWN,
    BenchError,
    BenchPlan,
    LoadedModel,
    image_min_tokens,
)
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from tests.bench.bench_fakes import RELEASED, REPLIES, fake_probes, stub_models
from tests.bench.conftest import run
from tests.judge.fake_vlm import FakeVlm
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
    assert len(record.protocol.sha256) == 64
    assert record.protocol.path.endswith("eval/PROTOCOL.md")
    assert record.specification.equals_tracked_clause_table
    assert (record.specification.clauses, record.specification.headings) == (16, 11)
    judge = record.judge
    assert (judge.model, judge.image_min_tokens, judge.gpu) == ("fake-vlm", "1024", "Fake GPU")
    assert (judge.cache_prompt, judge.corrections, judge.max_regions) == (False, "none recalled", 3)
    assert judge.server == {"model_file": "fake-q4.gguf"}
    assert json.loads(record.model_dump_json())["schema_version"] == 1


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
