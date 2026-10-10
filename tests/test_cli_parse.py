"""Tests for the `parse` verb of the command line."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from spec_to_inspector import cli
from spec_to_inspector.cli import app
from spec_to_inspector.spec.blocks import Paragraph
from spec_to_inspector.spec.markdown import read_markdown
from spec_to_inspector.spec.pdf import ParsedPdf
from spec_to_inspector.spec.schema import read_clause_table
from spec_to_inspector.spec.tokens import TokenizerError

SPECS = Path(__file__).resolve().parents[1] / "specs"
PDF = SPECS / "pcb-spec.pdf"
MARKDOWN = SPECS / "pcb-spec.md"
CLAUSE_TABLE = SPECS / "pcb-spec.clauses.json"

runner = CliRunner()

# docling 2.135.0 warns about fields of its own that it still reads.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def wide(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widen the consoles so no line of output is wrapped."""
    monkeypatch.setattr(cli.out, "width", 240)
    monkeypatch.setattr(cli.err, "width", 240)


@pytest.fixture
def fake_reader(monkeypatch: pytest.MonkeyPatch, wide: None) -> list[Path | None]:
    """Stand the Markdown source in for docling's reading of any PDF.

    Returns:
        The artefact directories the reader was called with.
    """
    calls: list[Path | None] = []

    def read(path: Path, *, artifacts_dir: Path | None = None) -> ParsedPdf:
        calls.append(artifacts_dir)
        text = MARKDOWN.read_text(encoding="utf-8")
        return ParsedPdf(blocks=tuple(read_markdown(text)), pages=1, text=text)

    monkeypatch.setattr(cli, "read_pdf", read)
    return calls


def test_parse_writes_the_clause_table_beside_the_pdf_and_prints_the_summary(
    fake_reader: list[Path | None], tmp_path: Path
) -> None:
    """A PDF in, the clause table out, and one line with pages, clauses and tokens."""
    pdf = tmp_path / "customer.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = runner.invoke(app, ["parse", str(pdf)])

    assert result.exit_code == 0, result.output
    table = read_clause_table(tmp_path / "customer.clauses.json")
    assert len(table.clauses) == 16
    assert "1 pages, 16 clauses under 11 numbered headings" in result.output
    assert "tokens (Qwen/Qwen3-VL-8B-Instruct)" in result.output
    assert "5.6.3" in result.output
    assert "wrong place" in result.output
    assert str(tmp_path / "customer.clauses.json") in result.output
    assert fake_reader == [None]


def test_parse_takes_its_outputs_and_docling_models_from_where_it_is_told(
    fake_reader: list[Path | None], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--out` and `--results` place the files; the settings place docling's models."""
    pdf = tmp_path / "customer.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_DOCLING_ARTIFACTS_DIR", str(tmp_path / "docling"))

    result = runner.invoke(
        app,
        [
            "parse",
            str(pdf),
            "--out",
            str(tmp_path / "a" / "table.json"),
            "--results",
            str(tmp_path / "b" / "spec.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "a" / "table.json").is_file()
    summary = json.loads((tmp_path / "b" / "spec.json").read_text(encoding="utf-8"))
    assert summary["clauses"] == 16
    assert summary["numbered_clauses"] == 11
    assert summary["document_tokens"] > summary["clause_table_tokens"] > 0
    assert fake_reader == [tmp_path / "docling"]


def test_parse_fails_on_a_file_that_is_not_a_pdf(wide: None, tmp_path: Path) -> None:
    """A missing file exits 1 with the cause and writes nothing."""
    result = runner.invoke(app, ["parse", str(tmp_path / "missing.pdf")])

    assert result.exit_code == 1
    assert "missing.pdf is not a file" in result.output
    assert list(tmp_path.iterdir()) == []


def test_parse_fails_on_a_pdf_that_is_not_a_specification(
    monkeypatch: pytest.MonkeyPatch, wide: None, tmp_path: Path
) -> None:
    """A document without the structure exits 1, says what is wrong and writes no table."""
    monkeypatch.setattr(
        cli,
        "read_pdf",
        lambda path, artifacts_dir=None: ParsedPdf(
            blocks=(Paragraph(text="A letter, not a specification.", page=1),), pages=1, text=""
        ),
    )
    pdf = tmp_path / "letter.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = runner.invoke(app, ["parse", str(pdf)])

    assert result.exit_code == 1
    assert "does not start with its title" in result.output
    assert not (tmp_path / "letter.clauses.json").exists()


def test_parse_still_writes_the_table_when_tokens_cannot_be_counted(
    fake_reader: list[Path | None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without the tokenizer the table is written and the summary says tokens are missing."""

    def unavailable(*args: object, **kwargs: object) -> None:
        raise TokenizerError("cannot load the tokenizer: offline")

    monkeypatch.setattr(cli, "summarise", unavailable)
    pdf = tmp_path / "customer.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = runner.invoke(app, ["parse", str(pdf)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "customer.clauses.json").is_file()
    assert "tokens not counted" in result.output
    assert "offline" in result.output

    asked = runner.invoke(app, ["parse", str(pdf), "--results", str(tmp_path / "spec.json")])

    assert asked.exit_code == 1
    assert not (tmp_path / "spec.json").exists()


def test_parse_of_the_tracked_pdf_gives_the_tracked_clause_table(
    wide: None, tmp_path: Path
) -> None:
    """End to end with docling: the demo PDF parses to the JSON the repository tracks."""
    result = runner.invoke(
        app,
        [
            "parse",
            str(PDF),
            "--out",
            str(tmp_path / "table.json"),
            "--results",
            str(tmp_path / "spec.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert read_clause_table(tmp_path / "table.json") == read_clause_table(CLAUSE_TABLE)
    assert "6 pages, 16 clauses under 11 numbered headings" in result.output
    summary = json.loads((tmp_path / "spec.json").read_text(encoding="utf-8"))
    assert summary["pages"] == 6
    assert summary["parts"]["pcb4"] == [
        "dirt",
        "missing",
        "extra",
        "wrong place",
        "damage",
        "scratch",
        "burnt",
    ]
