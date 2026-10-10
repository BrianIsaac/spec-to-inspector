"""Tests for the `serve` verb: the console built from the settings, and served for real."""

import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.cli import app
from tests.app.console_fakes import BATCH, World, write_world
from tests.judge.run_fakes import CATEGORY

runner = CliRunner()
LOOPBACK = "http://127.0.0.1:8130"


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The fake world, written once for the module.

    Returns:
        Where its files are.
    """
    return write_world(tmp_path_factory.mktemp("serve"))


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch, world: World, tmp_path: Path) -> dict[str, object]:
    """Point the settings at the fake world and catch what the verb hands to uvicorn.

    Returns:
        What `uvicorn.run` was called with, filled in when the verb runs.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(world.runs_dir))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_MODELS_DIR", str(world.models_dir))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli.out, "width", 400)
    monkeypatch.setattr(cli.err, "width", 400)
    seen: dict[str, object] = {}

    def run(application: FastAPI, **options: object) -> None:
        seen["app"] = application
        seen.update(options)

    monkeypatch.setattr(uvicorn, "run", run)
    return seen


def test_serve_hands_uvicorn_a_console_over_the_settings_directories(
    served: dict[str, object], world: World
) -> None:
    """The verb serves the runs and the models the settings name, on the host and port given."""
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--port", "9001"])  # noqa: S104

    assert result.exit_code == 0, result.output
    assert served["host"] == "0.0.0.0"  # noqa: S104
    assert served["port"] == 9001
    assert "http://0.0.0.0:9001/" in result.output
    application = served["app"]
    assert isinstance(application, FastAPI)
    client = TestClient(application, base_url=LOOPBACK, follow_redirects=False)
    assert client.get("/batch").headers["location"] == f"/batch/{CATEGORY}/{BATCH}"
    assert 'id="part-pcb9"' in client.get("/train").text
    assert "No specification is loaded" in client.get("/specification").text


def test_serve_listens_on_the_loopback_port_by_default(served: dict[str, object]) -> None:
    """Without options the console is for this machine alone."""
    result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0, result.output
    assert served["host"] == "127.0.0.1"
    assert served["port"] == 8130


def test_serve_starts_with_the_clause_table_it_is_given(
    served: dict[str, object], world: World
) -> None:
    """`--spec` puts a parsed specification in force from the first page."""
    result = runner.invoke(app, ["serve", "--spec", str(world.spec_path)])

    assert result.exit_code == 0, result.output
    application = served["app"]
    assert isinstance(application, FastAPI)
    page = TestClient(application, base_url=LOOPBACK).get("/specification")
    assert "Fake workmanship specification" in page.text


def test_serve_keeps_its_state_where_it_is_told(
    served: dict[str, object], world: World, tmp_path: Path
) -> None:
    """The console's own directory is `--state-dir`, and `.console` under the runs by default."""
    runner.invoke(app, ["serve"])
    by_default = served["app"]
    runner.invoke(app, ["serve", "--state-dir", str(tmp_path / "console-state")])
    told = served["app"]

    assert isinstance(by_default, FastAPI)
    assert isinstance(told, FastAPI)
    assert by_default.state.config.state_dir == world.runs_dir / ".console"
    assert told.state.config.state_dir == tmp_path / "console-state"
    assert told.state.config.runs_dir == world.runs_dir
    assert told.state.config.models_dir == world.models_dir


def test_serve_refuses_a_clause_table_it_cannot_read(
    served: dict[str, object], tmp_path: Path
) -> None:
    """A mistyped `--spec` stops the verb in words before anything is served."""
    result = runner.invoke(app, ["serve", "--spec", str(tmp_path / "absent.clauses.json")])

    assert result.exit_code == 1
    assert "absent.clauses.json" in result.output
    assert "app" not in served


def test_serve_refuses_a_port_that_is_not_one(served: dict[str, object]) -> None:
    """A port outside the range is a usage error."""
    result = runner.invoke(app, ["serve", "--port", "70000"])

    assert result.exit_code == 2
    assert "app" not in served


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_the_verb_serves_the_console_over_http_and_stops_on_a_signal(
    world: World, tmp_path: Path
) -> None:
    """Started as an operator would start it, the console answers and then shuts down cleanly."""
    port = _free_port()
    environment = {
        "PATH": "/usr/bin:/bin",
        "SPEC_TO_INSPECTOR_RUNS_DIR": str(world.runs_dir),
        "SPEC_TO_INSPECTOR_MODELS_DIR": str(world.models_dir),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from spec_to_inspector.cli import app; app()",
            "serve",
            "--port",
            str(port),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 60
        page = None
        while page is None:
            assert process.poll() is None, process.stdout.read() if process.stdout else ""
            assert time.monotonic() < deadline, "the console did not come up"
            try:
                page = httpx.get(f"http://127.0.0.1:{port}/batch/{CATEGORY}/{BATCH}", timeout=2)
            except httpx.TransportError:
                time.sleep(0.2)
        assert page.status_code == 200
        assert "Batch batch, part pcb9" in page.text
    finally:
        process.send_signal(signal.SIGINT)
        code = process.wait(timeout=30)
    assert code == 0


def test_a_console_on_the_loopback_address_refuses_another_host_name(
    served: dict[str, object],
) -> None:
    """Served for this machine alone, the console does not answer under a name that is not its."""
    runner.invoke(app, ["serve"])
    application = served["app"]
    assert isinstance(application, FastAPI)

    assert TestClient(application, base_url=LOOPBACK).get("/train").status_code == 200
    assert (
        TestClient(application, base_url="http://localhost:8130").get("/train").status_code == 200
    )
    assert (
        TestClient(application, base_url="http://evil.example:8130").get("/train").status_code
        == 400
    )


def test_a_console_served_to_a_network_answers_to_any_name(served: dict[str, object]) -> None:
    """On all interfaces the operator has said the network is trusted, and names are not checked."""
    runner.invoke(app, ["serve", "--host", "0.0.0.0"])  # noqa: S104
    application = served["app"]
    assert isinstance(application, FastAPI)

    assert (
        TestClient(application, base_url="http://inspector.lan:8130").get("/train").status_code
        == 200
    )
