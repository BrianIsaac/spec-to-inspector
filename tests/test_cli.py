"""Tests for the command line entry point."""

import pytest
from typer.testing import CliRunner

from spec_to_inspector.cli import app

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
