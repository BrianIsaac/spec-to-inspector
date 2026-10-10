"""Settings, read from the environment with the SPEC_TO_INSPECTOR_ prefix or from `.env`."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from spec_to_inspector.datasets.visa import VISA_URL


class Settings(BaseSettings):
    """Where the prototype keeps its data, weights and runs, and where it fetches from.

    Relative paths resolve against the working directory, which is the
    repository root in normal use; `data/`, `models/` and `runs/` there are
    ignored by git.

    Attributes:
        data_dir: Datasets, fetched by `spec-to-inspector data fetch`.
        models_dir: Trained models and downloaded weights.
        runs_dir: Outputs of training, inspection and benchmark runs.
        visa_url: The VisA tarball; a mirror may stand in for Amazon's bucket.
        docling_artifacts_dir: A directory holding docling's layout and table
            models, for a machine without network; unset, docling fetches
            them into the Hugging Face cache on first use.
        llama_cpp_dir: The llama.cpp clone and its build, made by
            `scripts/serve_vlm.sh`; the laptop's VLM server only.
        vlm_url: The judge's OpenAI-compatible server, up to and including
            `/v1`: llama.cpp's on the laptop, vLLM's or llm-scaler's on the B70.
        vlm_model: The model's name as that server knows it.
        vlm_timeout_seconds: How long one answer may take before the region
            is referred to an engineer.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPEC_TO_INSPECTOR_", env_file=".env", extra="ignore", frozen=True
    )

    data_dir: Path = Path("data")
    models_dir: Path = Path("models")
    runs_dir: Path = Path("runs")
    visa_url: str = VISA_URL
    docling_artifacts_dir: Path | None = None
    llama_cpp_dir: Path = Path("models/llama.cpp")
    vlm_url: str = "http://127.0.0.1:8131/v1"
    vlm_model: str = "qwen3-vl-8b-instruct"
    vlm_timeout_seconds: float = Field(default=120.0, gt=0)

    @field_validator("visa_url", "vlm_url")
    @classmethod
    def _http_only(cls, value: str, info: ValidationInfo) -> str:
        """Refuse a URL that httpx could not reach.

        Args:
            value: The configured URL.
            info: Which field is being validated.

        Returns:
            The URL, without a trailing slash for the VLM server's.

        Raises:
            ValueError: If the scheme is not http or https, or there is no host.
        """
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            msg = f"{info.field_name} must be an http or https URL, got {value!r}"
            raise ValueError(msg)
        return value.rstrip("/") if info.field_name == "vlm_url" else value

    @property
    def visa_dir(self) -> Path:
        """The directory that holds the kept VisA categories and their manifest."""
        return self.data_dir / "visa"
