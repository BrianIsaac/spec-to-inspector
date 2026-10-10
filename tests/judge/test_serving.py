"""Tests for what `scripts/serve_vlm.sh` reads from the settings."""

from pathlib import Path

import pytest

from spec_to_inspector.judge.serving import serving_lines
from spec_to_inspector.settings import Settings


@pytest.fixture(autouse=True)
def _no_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test from an empty directory so no `.env` file leaks in."""
    monkeypatch.chdir(tmp_path)
    for name in ("MODELS_DIR", "LLAMA_CPP_DIR", "VLM_URL", "VLM_MODEL"):
        monkeypatch.delenv(f"SPEC_TO_INSPECTOR_{name}", raising=False)


def test_the_lines_are_the_directories_the_address_and_the_model(tmp_path: Path) -> None:
    """The script reads five lines: two absolute paths, the host, the port and the model name."""
    lines = serving_lines(Settings())

    assert lines == [
        str(tmp_path / "models"),
        str(tmp_path / "models" / "llama.cpp"),
        "127.0.0.1",
        "8131",
        "qwen3-vl-8b-instruct",
    ]


def test_a_url_without_a_port_serves_on_the_scheme_default() -> None:
    """A server URL with no port means port 80, as a client would dial it."""
    settings = Settings(
        models_dir=Path("/srv/models"),
        llama_cpp_dir=Path("/srv/llama.cpp"),
        vlm_url="http://localhost/v1",
        vlm_model="judge",
    )

    assert serving_lines(settings) == ["/srv/models", "/srv/llama.cpp", "localhost", "80", "judge"]
