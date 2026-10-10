"""Tests for the judge's timing run and the figures file it writes."""

import json
from pathlib import Path

import pytest

from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import DECISION_NAME
from spec_to_inspector.judge.timing import (
    GpuReading,
    GpuSampler,
    JudgeResults,
    LiveAnswer,
    LiveRecord,
    TimingError,
    measure,
    parse_nvidia_smi,
    read_results,
    server_facts,
    spread,
    update_results,
)
from tests.judge.fake_vlm import FakeVlm, Reply
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

SPEC = specification()
REPLY = json.dumps(
    {
        "reason": "a thin bright line scored across the board face",
        "defect_class": "scratch",
        "clause_id": "4.1",
    }
)
TIMED = Reply(
    REPLY,
    usage={
        "prompt_tokens": 2400,
        "completion_tokens": 30,
        "prompt_tokens_details": {"cached_tokens": 2000},
    },
    timings={"predicted_per_second": 60.0, "prompt_ms": 100.0, "predicted_ms": 500.0},
)


def test_a_spread_gives_the_median_and_the_ninety_fifth_percentile() -> None:
    """Percentiles are numpy's, by linear interpolation between the ranked values."""
    figures = spread([4.0, 1.0, 3.0, 2.0, 5.0])

    assert figures.n == 5
    assert figures.p50 == 3.0
    assert figures.p95 == pytest.approx(4.8)
    assert figures.mean == 3.0
    assert figures.minimum == 1.0
    assert figures.maximum == 5.0


def test_a_spread_of_nothing_is_refused() -> None:
    """No figure is made from no measurement."""
    with pytest.raises(ValueError, match="no values"):
        spread([])


def _no_gpu() -> GpuReading:
    return GpuReading(gpu_used_mib=None, server_mib=None)


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A run with three flagged boards among five.

    Returns:
        The run's directory.
    """
    return write_run(
        tmp_path_factory.mktemp("timing"),
        {"good": "good", "speck": "speck", "scratch": "scratch", "two": "two", "fine": "good"},
    )


def test_each_flagged_image_is_asked_cold_and_then_cached(run: Path) -> None:
    """The cold pass switches the prompt cache off; a warm-up precedes the cached pass."""
    with FakeVlm(default=REPLY) as server, ChatClient(server.url, "fake-vlm") as client:
        timing = measure(run, SPEC, client, images=3, sampler=GpuSampler(_no_gpu))

    assert timing.images == 3
    assert [s.image_id for s in timing.cold] == ["speck", "scratch", "two"]
    assert [s.image_id for s in timing.cached] == ["speck", "scratch", "two"]
    switches = [request.get("cache_prompt") for request in server.requests]
    assert switches == [False, False, False, None, None, None, None]
    assert timing.cold_seconds.n == 3
    assert timing.cached_seconds.n == 3
    assert timing.cold_seconds.p50 == spread([s.seconds for s in timing.cold]).p50
    assert timing.warm_up_seconds > 0
    assert timing.category == "pcb9"
    assert timing.judge_model == "fake-vlm"


def test_only_region_one_is_asked_and_nothing_is_written(run: Path) -> None:
    """A timing run is one question per image and leaves the run as it found it."""
    with FakeVlm(default=REPLY) as server, ChatClient(server.url, "fake-vlm") as client:
        measure(run, SPEC, client, images=3, sampler=GpuSampler(_no_gpu))

    assert not list(run.glob(f"*/{DECISION_NAME}"))
    assert not list(run.glob("*/overlays"))


def test_the_servers_counts_are_summarised(run: Path) -> None:
    """Prompt tokens, cached tokens and the generation rate come from the server's own figures."""
    with FakeVlm(default=None, replies=[TIMED] * 7) as server, ChatClient(server.url, "m") as vlm:
        timing = measure(run, SPEC, vlm, images=3, sampler=GpuSampler(_no_gpu))

    assert timing.prompt_tokens is not None
    assert timing.prompt_tokens.p50 == 2400
    assert timing.cached_prompt_tokens is not None
    assert timing.cached_prompt_tokens.p50 == 2000
    assert timing.completion_tokens is not None
    assert timing.completion_tokens.p50 == 30
    assert timing.output_tokens_per_second is not None
    assert timing.output_tokens_per_second.p50 == 60.0
    assert timing.clause_prefix_tokens > 0


def test_fewer_flagged_images_than_asked_is_an_error(run: Path) -> None:
    """A figure over 20 images is not quietly made from 3."""
    with (
        FakeVlm(default=REPLY) as server,
        ChatClient(server.url, "fake-vlm") as client,
        pytest.raises(TimingError, match="3 flagged images"),
    ):
        measure(run, SPEC, client, images=20, sampler=GpuSampler(_no_gpu))


def test_a_server_that_cannot_be_asked_stops_the_run(run: Path) -> None:
    """A timing of referrals would be a timing of nothing."""
    with FakeVlm() as server:
        url = server.url
    with ChatClient(url, "fake-vlm") as client, pytest.raises(TimingError, match="cannot reach"):
        measure(run, SPEC, client, images=3, sampler=GpuSampler(_no_gpu))


def test_the_sampler_keeps_the_peak_of_what_it_reads() -> None:
    """The highest reading of the server's memory and of the card's is kept."""
    readings = iter(
        [
            GpuReading(gpu_used_mib=600, server_mib=None),
            GpuReading(gpu_used_mib=7400, server_mib=6800),
            GpuReading(gpu_used_mib=7900, server_mib=7300),
            GpuReading(gpu_used_mib=7700, server_mib=7100),
        ]
    )
    last = GpuReading(gpu_used_mib=7700, server_mib=7100)
    sampler = GpuSampler(lambda: next(readings, last), interval_seconds=0.01)

    with sampler:
        while sampler.samples < 4:
            pass

    memory = sampler.memory
    assert memory.gpu_before_mib == 600
    assert memory.server_peak_mib == 7300
    assert memory.gpu_peak_mib == 7900
    assert memory.samples >= 4
    assert memory.interval_seconds == 0.01


def test_nvidia_smi_output_is_read_for_the_card_and_the_server() -> None:
    """The card's used memory and the llama-server process's are picked out of the two queries."""
    reading = parse_nvidia_smi(
        "7412\n",
        "1234, /usr/bin/gnome-shell, 180\n"
        "88231, /home/u/llama.cpp/build/bin/llama-server, 6790\n"
        "90001, python, 620\n",
    )

    assert reading == GpuReading(gpu_used_mib=7412, server_mib=6790)
    assert parse_nvidia_smi("", "") == GpuReading(gpu_used_mib=None, server_mib=None)
    assert parse_nvidia_smi("N/A\n", "1, python, N/A\n") == GpuReading(None, None)


def _live() -> LiveRecord:
    return LiveRecord(
        measured_at="2026-10-11T00:00:00+00:00",
        command=["pytest", "-m", "live"],
        category="pcb9",
        run="runs/pcb9/test",
        judge_url="http://127.0.0.1:8131/v1",
        judge_model="qwen3-vl-8b-instruct",
        answers=[
            LiveAnswer(
                image_id="bad-000",
                label="bad",
                ground_truth=["scratch"],
                regions_found=1,
                regions_judged=1,
                outcome=Outcome.REJECT,
                reason="region 1: clause 4.2 rejects 'missing' in any zone, whatever its size",
                clause_id="4.2",
                judge_reason="an empty pad where a part should sit",
                judge_defect_class="missing",
                judge_clause_id="4.2",
                seconds=1.5,
            )
        ],
    )


def test_the_figures_file_keeps_each_writers_section(tmp_path: Path, run: Path) -> None:
    """The timing run and the live test each write their own part and leave the other's."""
    path = tmp_path / "results" / "judge.json"
    assert read_results(path) == JudgeResults()

    update_results(path, live=_live())
    with FakeVlm(default=REPLY) as server, ChatClient(server.url, "fake-vlm") as client:
        timing = measure(run, SPEC, client, images=3, sampler=GpuSampler(_no_gpu))
    update_results(path, timing=timing)

    stored = read_results(path)
    assert stored.live == _live()
    assert stored.timing == timing
    assert json.loads(path.read_text())["schema_version"] == 1
    assert "seconds" in stored.notes["units"]


def test_the_server_describes_itself_through_its_props() -> None:
    """llama.cpp's own account of its model, quantisation, context and build goes on record."""
    props = {
        "model_alias": "qwen3-vl-8b-instruct",
        "model_path": "/models/qwen3-vl-8b-instruct-gguf/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "model_ftype": "Q4_K - Medium",
        "build_info": "b1-d812350",
        "total_slots": 1,
        "default_generation_settings": {"n_ctx": 16384, "params": {"temperature": 0.8}},
        "chat_template": "{%- if tools %}",
    }
    with FakeVlm(props=props) as server:
        facts = server_facts(server.url)

    assert facts == {
        "model_alias": "qwen3-vl-8b-instruct",
        "model_file": "Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "model_ftype": "Q4_K - Medium",
        "build_info": "b1-d812350",
        "total_slots": "1",
        "n_ctx": "16384",
    }


def test_a_server_without_props_describes_nothing() -> None:
    """Another backend, or none, leaves the record empty instead of failing the run."""
    with FakeVlm() as server:
        assert server_facts(server.url) == {}
        url = server.url

    assert server_facts(url) == {}
