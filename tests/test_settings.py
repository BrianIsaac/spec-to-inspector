"""Tests for the settings read from the environment."""

from pathlib import Path

import pytest

from spec_to_inspector.datasets.visa import VISA_URL
from spec_to_inspector.settings import Settings


@pytest.fixture(autouse=True)
def _no_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test from an empty directory so no `.env` file leaks in."""
    monkeypatch.chdir(tmp_path)


def test_defaults_are_relative_to_the_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defaults keep data, weights and runs in the repository's ignored folders."""
    for name in ("DATA_DIR", "MODELS_DIR", "RUNS_DIR", "VISA_URL", "DOCLING_ARTIFACTS_DIR"):
        monkeypatch.delenv(f"SPEC_TO_INSPECTOR_{name}", raising=False)

    settings = Settings()

    assert settings.data_dir == Path("data")
    assert settings.models_dir == Path("models")
    assert settings.runs_dir == Path("runs")
    assert settings.visa_dir == Path("data/visa")
    assert settings.visa_url == VISA_URL
    assert settings.docling_artifacts_dir is None


def test_environment_overrides_the_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every setting can be moved with a SPEC_TO_INSPECTOR_ variable."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VISA_URL", "https://mirror.example/VisA.tar")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DOCLING_ARTIFACTS_DIR", str(tmp_path / "docling"))

    settings = Settings()

    assert settings.data_dir == tmp_path / "d"
    assert settings.visa_dir == tmp_path / "d" / "visa"
    assert settings.visa_url == "https://mirror.example/VisA.tar"
    assert settings.docling_artifacts_dir == tmp_path / "docling"


def test_a_url_that_is_not_http_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mistyped mirror fails at start-up, not halfway through a download."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VISA_URL", "file:///etc/passwd")

    with pytest.raises(ValueError, match="http"):
        Settings()


def test_a_dot_env_file_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A `.env` in the working directory sets values the environment leaves unset."""
    monkeypatch.delenv("SPEC_TO_INSPECTOR_RUNS_DIR", raising=False)
    (tmp_path / ".env").write_text("SPEC_TO_INSPECTOR_RUNS_DIR=/srv/runs\n")

    assert Settings().runs_dir == Path("/srv/runs")
