"""Tests for reading which vLLM server answered, against a stand-in `docker` and a fake server.

The strings are what the machine printed on 7 November 2026: the server's endpoints, `docker
inspect` and the server's log.
"""

import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from spec_to_inspector.judge.vllm_server import (
    OWN_MINIMUM,
    UNKNOWN,
    PrefixCacheCounters,
    ServerReading,
    log_hit_rates,
    parse_counters,
    read_counters,
    read_log,
    read_server,
)
from spec_to_inspector.settings import Settings
from tests.bench.bench_fakes import COLD_FLAGS
from tests.judge.fake_vlm import FakeVlm

DIGEST = "sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490"
REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
SNAPSHOT = f"/root/.cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/{REVISION}"
VERSION = "0.26.1.dev0+g568afb3a1.d20260831"
COMMAND = (
    "source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; exec vllm serve "
    f"            --model {SNAPSHOT}"
    "             --served-model-name qwen3-vl-8b-instruct"
    "             --dtype=float16"
    "             --port 8131"
    "             --gpu-memory-util=0.9"
    "             --mm-processor-kwargs "
    """'{"size": {"shortest_edge": 1048576, "longest_edge": 16777216}}'"""
    "             --no-enable-prefix-caching --mm-processor-cache-gb 0"
    "             -tp=1"
)
LABELS = {
    "org.opencontainers.image.revision": "ac12083301cbdbe06135882d401f7877b0b512db",
    "org.opencontainers.image.title": "Open Middleware X<sup>e</sup>",
    "org.opencontainers.image.version": "20260608",
}
STARTED = "2026-11-06T15:40:16.517468169Z"
METRICS = """\
# HELP vllm:prefix_cache_queries_total Prefix cache queries, in terms of number of queried tokens.
# TYPE vllm:prefix_cache_queries_total counter
vllm:prefix_cache_queries_total{engine="0",model_name="qwen3-vl-8b-instruct"} 0.0
vllm:prefix_cache_queries_created{engine="0",model_name="qwen3-vl-8b-instruct"} 1.79e+09
vllm:prefix_cache_hits_total{engine="0",model_name="qwen3-vl-8b-instruct"} 0.0
"""
ENGINE = (
    "(EngineCore pid=919) INFO 11-06 15:40:43 [core.py:116] Initializing a V1 LLM engine "
    f"(v{VERSION}) with config: model='{SNAPSHOT}', trust_remote_code=True, dtype=torch.float16, "
    "max_seq_len=32768, quantization=None, seed=0, served_model_name=qwen3-vl-8b-instruct, "
    "enable_prefix_caching=False, enable_chunked_prefill=True, pooler_config=None"
)
RATE_LINE = (
    "(APIServer pid=1) INFO 11-06 19:54:40 [loggers.py:310] Engine 000: Avg prompt throughput: "
    "934.6 tokens/s, Avg generation throughput: 5.8 tokens/s, Running: 1 reqs, Waiting: 0 reqs, "
    "GPU KV cache usage: 10.7%, Prefix cache hit rate: {rate}%"
)


def _vllm(metrics: str = METRICS) -> FakeVlm:
    return FakeVlm(
        routes={
            "/version": json.dumps({"version": VERSION}),
            "/v1/models": json.dumps(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "qwen3-vl-8b-instruct",
                            "created": 1793997797,
                            "root": SNAPSHOT,
                            "max_model_len": 32768,
                        }
                    ],
                }
            ),
            "/metrics": metrics,
        }
    )


def _docker(
    directory: Path,
    *,
    command: str = COMMAND,
    running: bool = True,
    log: str = ENGINE,
    digests: tuple[str, ...] = (f"intel/llm-scaler-vllm@{DIGEST}",),
) -> str:
    """Write a stand-in `docker` that prints what the machine's does.

    Args:
        directory: Where to write it.
        command: The container's command line.
        running: Whether the container is running.
        log: The container's log.
        digests: The image's digests.

    Returns:
        Its path.
    """
    container = [
        {
            "Args": ["-c", command],
            "Image": DIGEST,
            "State": {"Running": running, "StartedAt": STARTED},
            "Config": {"Image": "intel/llm-scaler-vllm:0.26.0-b1", "Labels": LABELS},
        }
    ]
    (directory / "container.json").write_text(json.dumps(container), encoding="utf-8")
    (directory / "image.json").write_text(json.dumps([{"RepoDigests": digests}]), encoding="utf-8")
    (directory / "log.txt").write_text(log, encoding="utf-8")
    path = directory / "fake-docker"
    path.write_text(
        f"""#!/bin/sh
echo "$@" >> {directory}/asked.txt
case "$1" in
inspect) cat {directory}/container.json ;;
image) cat {directory}/image.json ;;
logs) cat {directory}/log.txt ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def _port_of(server: FakeVlm) -> str:
    return server.url.removesuffix("/v1").rpartition(":")[2]


def test_each_fact_is_read_from_where_it_lives_and_says_so(tmp_path: Path) -> None:
    """The endpoints what they give; the container the image; the engine's line the precision."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        reading = read_server(
            server.url, "spec-to-inspector-vlm", docker=_docker(tmp_path, command=command)
        )

    facts = reading.facts
    assert facts["vllm_version"] == VERSION
    assert facts["served_model"] == "qwen3-vl-8b-instruct"
    assert facts["weights_revision"] == REVISION
    assert facts["max_model_len"] == "32768"
    assert facts["image"] == "intel/llm-scaler-vllm:0.26.0-b1"
    assert facts["image_digest"] == DIGEST
    assert facts["dtype"] == "float16"
    assert facts["image_label_version"] == "20260608"
    assert "--gpu-memory-util=0.9" in facts["command"]
    assert "  " not in facts["command"]
    assert reading.sources["vllm_version"] == "GET /version"
    assert reading.sources["weights_revision"] == "GET /v1/models"
    assert reading.sources["image"] == "docker inspect, Config.Image"
    assert reading.sources["image_digest"] == "docker image inspect, RepoDigests"
    assert reading.sources["dtype"].startswith("the server's log")
    assert reading.sources["image_label_version"].startswith("container label")
    assert set(reading.sources) == set(facts)


def test_the_image_size_and_the_cold_come_from_the_servers_start(tmp_path: Path) -> None:
    """1,048,576 pixels at 32 by 32 a token is 1,024 tokens; the flags and the engine say cold."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        reading = read_server(server.url, "c", docker=_docker(tmp_path, command=command))

    assert reading.image_min_tokens == "1024"
    assert reading.cold_flags == ("--no-enable-prefix-caching", "--mm-processor-cache-gb 0")
    assert reading.engine_prefix_caching is False
    assert reading.started_at == STARTED


def test_the_comparisons_image_minimum_reads_as_its_own(tmp_path: Path) -> None:
    """`IMAGE_MIN_PIXELS=65536` is 64 tokens; a server with no setting has the model's own."""
    with _vllm() as server:
        port = f"--port {_port_of(server)}"
        started = COMMAND.replace("--port 8131", port)
        smaller = read_server(
            server.url,
            "c",
            docker=_docker(tmp_path, command=started.replace("1048576", "65536")),
        )
        bare = read_server(
            server.url,
            "c",
            docker=_docker(tmp_path, command=f"vllm serve --dtype=float16 {port}"),
        )
    assert smaller.image_min_tokens == "64"
    assert bare.image_min_tokens == OWN_MINIMUM
    assert bare.cold_flags == ()


def test_a_restart_changes_no_fact(tmp_path: Path) -> None:
    """The third run follows a restart and must still read as the same making."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        reading = read_server(server.url, "c", docker=_docker(tmp_path, command=command))
    assert STARTED not in reading.facts.values()
    assert not any("1793997797" in value for value in reading.facts.values())


def test_a_container_that_does_not_serve_this_port_is_not_taken_for_the_server(
    tmp_path: Path,
) -> None:
    """The server's own word is kept, and nothing is claimed from a container that cannot be it."""
    with _vllm() as server:
        reading = read_server(server.url, "c", docker=_docker(tmp_path))

    assert reading.facts["vllm_version"] == VERSION
    assert "image" not in reading.facts
    assert "dtype" not in reading.facts
    assert reading.image_min_tokens == UNKNOWN
    assert reading.cold_flags == ()
    assert reading.started_at is None


def test_a_stopped_container_and_no_docker_claim_nothing(tmp_path: Path) -> None:
    """Without Docker the record says what it could not read, rather than guessing."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        stopped = read_server(
            server.url, "c", docker=_docker(tmp_path, command=command, running=False)
        )
        absent = read_server(server.url, "c", docker=None)
    assert "image" not in stopped.facts
    assert "image" not in absent.facts
    assert absent.image_min_tokens == UNKNOWN


def test_a_server_that_is_not_vllm_gives_nothing_from_its_endpoints(tmp_path: Path) -> None:
    """A 404 on every path is no facts at all, and no error."""
    with FakeVlm() as server:
        assert read_server(server.url, "c", docker=None).facts == {}
        assert read_counters(server.url) is None


def test_the_precision_falls_back_to_what_the_command_asked(tmp_path: Path) -> None:
    """Where the engine's line has gone from the log, the flag is read and says it is the flag."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        reading = read_server(server.url, "c", docker=_docker(tmp_path, command=command, log=""))
    assert reading.facts["dtype"] == "float16"
    assert reading.sources["dtype"] == "docker inspect, Args, --dtype"
    assert reading.engine_prefix_caching is None


def _quantisation_read(tmp_path: Path, *, log: str, flag: str = "") -> ServerReading:
    """Read a server whose engine's line and command line are as given.

    Args:
        tmp_path: Where to write the stand-in `docker`.
        log: The container's log.
        flag: What to add to the container's command line.

    Returns:
        What was read.
    """
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)} {flag}")
        return read_server(server.url, "c", docker=_docker(tmp_path, command=command, log=log))


def test_the_engines_line_says_which_quantisation_it_runs_at(tmp_path: Path) -> None:
    """Its word and not the weights' path: `None` is what the engine says of the FP16 final."""
    final = _quantisation_read(tmp_path, log=ENGINE)
    fp8 = _quantisation_read(tmp_path, log=ENGINE.replace("quantization=None", "quantization=fp8"))

    assert final.facts["quantisation"] == "None"
    assert fp8.facts["quantisation"] == "fp8"
    assert fp8.facts["dtype"] == "float16"
    assert fp8.sources["quantisation"] == "the server's log, the engine's line, quantization=*"


def test_the_quantisation_falls_back_to_the_flag_and_is_otherwise_not_guessed(
    tmp_path: Path,
) -> None:
    """Without the line the flag says what was asked; with neither, the fact is left out."""
    asked = _quantisation_read(tmp_path, log="", flag="--quantization fp8")
    neither = _quantisation_read(tmp_path, log="")
    fp8_weights = _quantisation_read(tmp_path, log="", flag="--served-model-name x-FP8")

    assert asked.facts["quantisation"] == "fp8"
    assert asked.sources["quantisation"] == "docker inspect, Args, --quantization"
    assert "quantisation" not in neither.facts
    assert "quantisation" not in neither.sources
    assert "quantisation" not in fp8_weights.facts


def test_a_line_with_no_word_on_the_quantisation_falls_back_too(tmp_path: Path) -> None:
    """An engine that does not print it says nothing either way."""
    silent = ENGINE.replace("quantization=None, ", "")

    assert "quantisation" not in _quantisation_read(tmp_path, log=silent).facts
    assert (
        _quantisation_read(tmp_path, log=silent, flag="-q fp8").sources["quantisation"]
        == "docker inspect, Args, --quantization"
    )


@pytest.mark.parametrize(
    ("kept", "word"),
    [
        ("comparison-fp8/raw/server-fp8-whole.txt", "fp8"),
        ("comparison-image-minimum/raw/server-image-minimum-whole.txt", "None"),
        ("comparison-designators/raw/server-designators-whole.txt", "None"),
        ("final/raw/server-before-restart.txt", "None"),
    ],
)
def test_the_server_logs_kept_of_the_runs_give_the_field_as_the_reader_would(
    tmp_path: Path, kept: str, word: str
) -> None:
    """The machine's own lines, kept under each folder's `raw/`, through the same code path."""
    results = Path(__file__).parents[2] / "results" / "stage2"
    log = (results / kept).read_text(encoding="utf-8", errors="replace")

    reading = _quantisation_read(tmp_path, log=log)

    assert reading.facts["quantisation"] == word
    assert reading.facts["dtype"] == "float16"


def test_an_image_with_no_repository_digest_is_named_by_its_id(tmp_path: Path) -> None:
    """A locally built image has no entry in RepoDigests; its id is all there is."""
    with _vllm() as server:
        command = COMMAND.replace("--port 8131", f"--port {_port_of(server)}")
        reading = read_server(
            server.url, "c", docker=_docker(tmp_path, command=command, digests=())
        )
    assert reading.facts["image_digest"] == DIGEST
    assert reading.sources["image_digest"] == "docker inspect, Image"


def test_the_counters_are_read_from_the_metrics_page() -> None:
    """With the cache off vLLM counts nothing at all: 0 of 0, not a rate of 0%."""
    assert parse_counters(METRICS) == PrefixCacheCounters(hits=0, queries=0)
    with _vllm(
        METRICS.replace(
            'hits_total{engine="0",model_name="qwen3-vl-8b-instruct"} 0.0',
            'hits_total{engine="0"} 4121.0',
        )
    ) as server:
        assert read_counters(server.url) == PrefixCacheCounters(hits=4121, queries=0)


def test_counters_that_are_not_there_are_not_read_as_zero() -> None:
    """Nothing printed is unknown, which the record must not call a clean run."""
    assert parse_counters("") is None
    assert parse_counters('vllm:prefix_cache_hits_total{engine="0"} 0.0\n') is None
    assert parse_counters('vllm:prefix_cache_hits_total{engine="0"} nope\n') is None


def test_every_rate_the_log_prints_is_found() -> None:
    """Week 1's two logs: all 0.0% started cold, 92.4% with vLLM's defaults."""
    log = "\n".join(
        [ENGINE, RATE_LINE.format(rate="0.0"), "GET /metrics", RATE_LINE.format(rate="92.4")]
    )
    assert log_hit_rates(log) == [0.0, 92.4]
    assert log_hit_rates("nothing here") == []


def test_the_log_is_asked_for_from_the_moment_named(tmp_path: Path) -> None:
    """Docker reads the moment in UTC, to the second."""
    docker = _docker(tmp_path, log=RATE_LINE.format(rate="0.0"))
    moment = datetime(2026, 11, 7, 1, 2, 3, 900, tzinfo=UTC)

    assert read_log("c", moment, docker=docker) == RATE_LINE.format(rate="0.0")
    assert (tmp_path / "asked.txt").read_text(encoding="utf-8").split() == [
        "logs",
        "--since",
        "2026-11-07T01:02:03Z",
        "c",
    ]
    assert read_log("c", moment, docker=None) is None


def test_a_docker_that_fails_gives_nothing(tmp_path: Path) -> None:
    """A failed command is the same as no Docker: nothing read, nothing raised."""
    failing = tmp_path / "fake-docker"
    failing.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    failing.chmod(failing.stat().st_mode | stat.S_IXUSR)

    assert read_log("c", datetime.now(UTC), docker=str(failing)) is None
    assert read_server("http://127.0.0.1:9/v1", "c", docker=str(failing)).facts == {}


def test_the_serving_script_starts_what_this_reader_looks_for() -> None:
    """The container's name and the cold flags are in two places; they must be one."""
    script = (Path(__file__).parents[2] / "scripts" / "serve_vlm_xpu.sh").read_text(
        encoding="utf-8"
    )

    assert f'CONTAINER="{Settings.model_fields["vlm_container"].default}"' in script
    for flag in COLD_FLAGS:
        assert flag in script
    assert "--port $PORT" in script
    assert "--dtype=float16" in script


def test_the_serving_script_no_longer_sets_the_machine_against_the_laptop() -> None:
    """The two sentences ruling 2 and week 1 made stale."""
    script = (Path(__file__).parents[2] / "scripts" / "serve_vlm_xpu.sh").read_text(
        encoding="utf-8"
    )

    assert "the server is two settings" not in script
    assert "no figure compares" not in script
    assert "the laptop's area" not in script
