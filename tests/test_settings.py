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
    for name in (
        "DATA_DIR",
        "MODELS_DIR",
        "RUNS_DIR",
        "VISA_URL",
        "DOCLING_ARTIFACTS_DIR",
        "LLAMA_CPP_DIR",
        "VLM_URL",
        "VLM_MODEL",
        "VLM_TIMEOUT_SECONDS",
        "CORRECTIONS_DB",
        "CORRECTIONS_RECALL",
    ):
        monkeypatch.delenv(f"SPEC_TO_INSPECTOR_{name}", raising=False)

    settings = Settings()

    assert settings.data_dir == Path("data")
    assert settings.models_dir == Path("models")
    assert settings.runs_dir == Path("runs")
    assert settings.visa_dir == Path("data/visa")
    assert settings.visa_url == VISA_URL
    assert settings.docling_artifacts_dir is None
    assert settings.llama_cpp_dir == Path("models/llama.cpp")
    assert settings.vlm_url == "http://127.0.0.1:8131/v1"
    assert settings.vlm_model == "qwen3-vl-8b-instruct"
    assert settings.vlm_timeout_seconds == 120.0
    assert settings.corrections_db is None
    assert settings.corrections_path == Path("runs/corrections.sqlite3")
    assert settings.corrections_recall == "part"


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


def test_the_judge_backend_is_a_url_and_a_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Another OpenAI-compatible server, such as vLLM on the B70, is two variables away."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_URL", "http://b70.example:8000/v1/")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_TIMEOUT_SECONDS", "30")

    settings = Settings()

    assert settings.vlm_url == "http://b70.example:8000/v1"
    assert settings.vlm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.vlm_timeout_seconds == 30.0


@pytest.mark.parametrize("url", ["ftp://127.0.0.1/v1", "127.0.0.1:8131", "http:///v1"])
def test_a_judge_url_that_is_not_http_is_refused(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """A mistyped server address fails at start-up, not at the first board."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_URL", url)

    with pytest.raises(ValueError, match="http"):
        Settings()


def test_a_judge_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout of zero would fail every request."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="greater than 0"):
        Settings()


def test_the_corrections_store_follows_the_runs_directory_unless_moved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One file, copied with the runs; a variable puts it elsewhere."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(tmp_path / "r"))
    assert Settings().corrections_path == tmp_path / "r" / "corrections.sqlite3"

    monkeypatch.setenv("SPEC_TO_INSPECTOR_CORRECTIONS_DB", str(tmp_path / "demo.sqlite3"))
    assert Settings().corrections_path == tmp_path / "demo.sqlite3"


def test_the_recall_strategy_is_one_of_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """Recall by part or on the answer; anything else is refused."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_CORRECTIONS_RECALL", "answer")
    assert Settings().corrections_recall == "answer"

    monkeypatch.setenv("SPEC_TO_INSPECTOR_CORRECTIONS_RECALL", "always")
    with pytest.raises(ValueError, match="corrections_recall"):
        Settings()
