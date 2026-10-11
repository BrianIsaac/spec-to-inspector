"""The Specification page with the real parser: the tracked PDF through docling, by upload."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spec_to_inspector.app.server import build_console
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import read_clause_table

# docling 2.135.0 raises deprecation notices about its own options while it converts, as in
# tests/spec/test_pdf.py.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

SPEC_PDF = Path("specs/pcb-spec.pdf")
CLAUSE_TABLE = Path("specs/pcb-spec.clauses.json")


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fresh state directory for the module's console.

    Returns:
        The directory.
    """
    return tmp_path_factory.mktemp("parse") / "state"


@pytest.fixture(scope="module")
def client(state_dir: Path) -> TestClient:
    """A console as `serve` builds it, with a fresh state directory and no specification.

    Returns:
        Its client.
    """
    root = state_dir.parent
    settings = Settings(runs_dir=root / "runs", models_dir=root / "models", data_dir=root / "data")
    return TestClient(build_console(settings, state_dir=state_dir), follow_redirects=False)


def test_an_unreadable_pdf_is_refused_with_the_parser_own_words(client: TestClient) -> None:
    """A file that begins like a PDF and is not one is refused by docling, and said on the page."""
    response = client.post(
        "/specification",
        files={"pdf": ("broken.pdf", b"%PDF-1.7\nnot really a document\n", "application/pdf")},
    )

    assert response.status_code == 422
    assert "The upload was refused" in response.text
    assert "broken.pdf" in response.text
    assert "No specification is loaded" in response.text


def test_the_tracked_specification_uploads_into_its_clause_table(
    client: TestClient, state_dir: Path
) -> None:
    """The demo PDF, uploaded, gives the clause table that is tracked beside it, and its pages."""
    tracked = read_clause_table(CLAUSE_TABLE)

    response = client.post(
        "/specification", files={"pdf": (SPEC_PDF.name, SPEC_PDF.read_bytes(), "application/pdf")}
    )
    page = client.get("/specification", params={"clause": "5.6.1"})

    assert response.status_code == 303
    assert page.status_code == 200
    assert page.text.count('class="clause-row') == len(tracked.clauses) == 16
    for clause in tracked.clauses:
        assert f'id="clause-{clause.id}"' in page.text
    assert tracked.title in page.text
    assert "Page 5 of 6" in page.text
    sheet = client.get("/specification/pages/5.png")
    assert sheet.status_code == 200
    assert sheet.content.startswith(b"\x89PNG")
    kept = read_clause_table(state_dir / "specification.clauses.json")
    assert kept == tracked
