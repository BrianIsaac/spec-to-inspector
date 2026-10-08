"""Tests for the command line entry point."""

from functools import partial
from pathlib import Path

import pytest
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.cli import app
from spec_to_inspector.datasets.visa import MANIFEST_NAME, fetch_visa
from tests.datasets.visa_fakes import EXPECTED, NO_WAIT, FakeServer, fake_files, make_tar

runner = CliRunner()


def test_help_lists_every_verb() -> None:
    """The top-level help names the six verbs of the pipeline."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for verb in ("data", "parse", "train", "inspect", "bench", "serve"):
        assert verb in result.output


@pytest.mark.parametrize(
    ("verb", "unit"),
    [("parse", "U3"), ("train", "U2"), ("inspect", "U5"), ("bench", "U7"), ("serve", "U8")],
)
def test_stubbed_verbs_fail_and_name_their_unit(verb: str, unit: str) -> None:
    """A verb not built yet exits non-zero and says which unit builds it."""
    result = runner.invoke(app, [verb])

    assert result.exit_code == 1
    assert "not built yet" in result.output
    assert unit in result.output


def test_data_help_lists_fetch() -> None:
    """The data group offers the fetch command."""
    result = runner.invoke(app, ["data", "--help"])

    assert result.exit_code == 0
    assert "fetch" in result.output


@pytest.fixture
def data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the settings at a temporary data directory and the fetch at a fake server.

    Returns:
        The data directory.
    """
    server = FakeServer(make_tar(fake_files()), drops=[])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.out, "width", 240)
    monkeypatch.setattr(cli.err, "width", 240)
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        cli,
        "fetch_visa",
        partial(
            fetch_visa,
            expected=EXPECTED,
            expected_bytes=len(server.body),
            transport=server.transport(),
            retry_delays=NO_WAIT,
        ),
    )
    return tmp_path / "data"


def test_data_fetch_streams_verifies_and_prints_the_counts(data_dir: Path) -> None:
    """A first fetch reports the counts per category and where the manifest is."""
    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    assert (data_dir / "visa" / MANIFEST_NAME).is_file()
    assert "Streamed" in result.output
    assert "pcb4" in result.output
    assert "wrong place 1" in result.output
    assert MANIFEST_NAME in result.output


def test_data_fetch_twice_re_verifies(data_dir: Path) -> None:
    """A second fetch re-verifies and says so."""
    runner.invoke(app, ["data", "fetch"])

    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    assert "Re-verified" in result.output


def test_data_fetch_fails_on_a_changed_tree_and_names_the_way_out(data_dir: Path) -> None:
    """A changed file makes the fetch exit 1 with the difference and the --force hint."""
    runner.invoke(app, ["data", "fetch"])
    (data_dir / "visa/pcb1/Data/Images/Normal/0000.JPG").write_bytes(b"changed")

    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 1
    assert "tree digest differs" in result.output
    assert "--force" in result.output


def test_data_fetch_reports_progress_in_tenths_without_a_terminal(data_dir: Path) -> None:
    """Without a terminal the bar is hidden, so plain lines mark each tenth of the stream."""
    result = runner.invoke(app, ["data", "fetch"])

    assert result.exit_code == 0, result.output
    tenths = [line for line in result.output.splitlines() if line.startswith("Received ")]
    assert len(tenths) == 10
    assert tenths[-1].endswith("(100%)")
