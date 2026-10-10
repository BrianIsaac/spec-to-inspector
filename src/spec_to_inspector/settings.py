"""Settings, read from the environment with the SPEC_TO_INSPECTOR_ prefix or from `.env`."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
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
    """

    model_config = SettingsConfigDict(
        env_prefix="SPEC_TO_INSPECTOR_", env_file=".env", extra="ignore", frozen=True
    )

    data_dir: Path = Path("data")
    models_dir: Path = Path("models")
    runs_dir: Path = Path("runs")
    visa_url: str = VISA_URL
    docling_artifacts_dir: Path | None = None

    @field_validator("visa_url")
    @classmethod
    def _http_only(cls, value: str) -> str:
        """Refuse a URL that httpx could not stream.

        Args:
            value: The configured URL.

        Returns:
            The URL unchanged.

        Raises:
            ValueError: If the scheme is not http or https, or there is no host.
        """
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            msg = f"visa_url must be an http or https URL, got {value!r}"
            raise ValueError(msg)
        return value

    @property
    def visa_dir(self) -> Path:
        """The directory that holds the kept VisA categories and their manifest."""
        return self.data_dir / "visa"
