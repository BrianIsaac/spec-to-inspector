"""Tests for the measured summary of a parse."""

from pathlib import Path

from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit

from spec_to_inspector.spec.pdf import ParsedPdf
from spec_to_inspector.spec.summary import ParseSummary, clause_table_text, summarise
from tests.spec.spec_fakes import specification


def words() -> Tokenizer:
    """Build a tokenizer that counts white-space separated words.

    Returns:
        The tokenizer.
    """
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))  # noqa: S106
    tokenizer.pre_tokenizer = WhitespaceSplit()  # pyright: ignore[reportAttributeAccessIssue]
    return tokenizer


def test_the_summary_counts_pages_clauses_and_tokens(tmp_path: Path) -> None:
    """The figures the deck quotes come from the parse itself, with what measured them."""
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    spec = specification()
    parsed = ParsedPdf(blocks=(), pages=3, text="one two three four five six")

    summary = summarise(pdf, parsed, spec, parse_seconds=1.23456, tokenizer=words())

    assert summary.pages == 3
    assert summary.clauses == 3
    assert summary.numbered_clauses == 2
    assert summary.zones == 2
    assert summary.parts == {"pcb9": ["scratch", "missing"]}
    assert summary.document_tokens == 6
    assert summary.tokens_per_page == 2.0
    assert summary.clause_table_tokens == len(clause_table_text(spec).split())
    assert summary.tokenizer == "given"
    assert summary.parse_seconds == 1.235
    assert summary.pdf_bytes == 13
    assert len(summary.pdf_sha256) == 64
    assert summary.parser.startswith("docling ")
    assert summary.device == "cpu"


def test_the_clause_table_text_is_compact_json_of_every_clause() -> None:
    """The clause table is counted as the compact JSON a prompt would carry."""
    text = clause_table_text(specification())

    assert text.startswith('[{"id":"4.1.1"')
    assert '"limit":0.5' in text
    assert "\n" not in text


def test_the_summary_round_trips_through_its_file(tmp_path: Path) -> None:
    """The results file is JSON that reads back to the same summary."""
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    parsed = ParsedPdf(blocks=(), pages=3, text="one two")
    summary = summarise(pdf, parsed, specification(), parse_seconds=2.0, tokenizer=words())
    path = tmp_path / "results" / "spec.json"

    summary.write(path)

    assert ParseSummary.model_validate_json(path.read_text(encoding="utf-8")) == summary
    assert path.read_text(encoding="utf-8").endswith("}\n")
