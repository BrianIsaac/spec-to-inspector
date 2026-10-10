"""The measured summary of a parse: the figures the deck and the README quote.

Everything here is counted from one parse of one PDF: its pages, its clauses,
its size in the judge's tokens and the time docling took. It is written to
`results/stage1/spec.json` so the figures outlive the working tree.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from tokenizers import Tokenizer

from spec_to_inspector.spec.pdf import MAX_THREADS, ParsedPdf
from spec_to_inspector.spec.schema import Specification
from spec_to_inspector.spec.tokens import VLM_TOKENIZER, count_tokens


class ParseSummary(BaseModel):
    """What one parse of a specification measured.

    Attributes:
        specification: The PDF's path as given.
        pdf_sha256: The PDF's digest.
        pdf_bytes: The PDF's size.
        pages: The number of pages.
        clauses: The rows of the clause table.
        numbered_clauses: The numbered clause headings: one per defect class per part.
        zones: The zones declared, over every part.
        parts: The defect classes of each part, in document order.
        document_tokens: The whole document's text, as docling exports it to
            Markdown, in the tokenizer's tokens; figures are not counted.
        tokens_per_page: `document_tokens` over `pages`.
        clause_table_tokens: The clause table as compact JSON, in the same tokens.
        tokenizer: The tokenizer the tokens are counted in.
        parse_seconds: Wall time of docling's conversion and the extraction,
            models loaded from disk, in the process that parsed.
        parser: The parser and its version.
        device: Where the parser ran.
        threads: The CPU threads it was given.
        measured_at: When, in UTC.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    specification: str
    pdf_sha256: str
    pdf_bytes: int
    pages: int
    clauses: int
    numbered_clauses: int
    zones: int
    parts: dict[str, list[str]]
    document_tokens: int
    tokens_per_page: float
    clause_table_tokens: int
    tokenizer: str
    parse_seconds: float
    parser: str
    device: str
    threads: int
    measured_at: datetime

    def write(self, path: Path) -> None:
        """Write the summary as JSON, creating the directory if needed.

        Args:
            path: Where to write it.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")


def clause_table_text(specification: Specification) -> str:
    """Give the clause table as the compact JSON a prompt would carry.

    Args:
        specification: The parsed specification.

    Returns:
        A JSON array of the clauses, without white space.
    """
    rows = [clause.model_dump(mode="json") for clause in specification.clauses]
    return json.dumps(rows, separators=(",", ":"), ensure_ascii=False)


def summarise(
    pdf: Path,
    parsed: ParsedPdf,
    specification: Specification,
    *,
    parse_seconds: float,
    tokenizer: str | Tokenizer = VLM_TOKENIZER,
) -> ParseSummary:
    """Measure a parse.

    Args:
        pdf: The PDF that was parsed.
        parsed: What docling read from it.
        specification: The specification extracted from it.
        parse_seconds: How long the parse took.
        tokenizer: The tokenizer to count in, or the repository to load it from.

    Returns:
        The summary.

    Raises:
        TokenizerError: If the named tokenizer cannot be loaded.
    """
    content = pdf.read_bytes()
    document_tokens = count_tokens(parsed.text, tokenizer=tokenizer)
    return ParseSummary(
        specification=str(pdf),
        pdf_sha256=hashlib.sha256(content).hexdigest(),
        pdf_bytes=len(content),
        pages=specification.pages,
        clauses=len(specification.clauses),
        numbered_clauses=len({clause.heading_id for clause in specification.clauses}),
        zones=len(specification.zones),
        parts={
            part: list(specification.defect_classes(part)) for part in specification.categories()
        },
        document_tokens=document_tokens,
        tokens_per_page=round(document_tokens / specification.pages, 1),
        clause_table_tokens=count_tokens(clause_table_text(specification), tokenizer=tokenizer),
        tokenizer=tokenizer if isinstance(tokenizer, str) else "given",
        parse_seconds=round(parse_seconds, 3),
        parser=f"docling {metadata.version('docling')}",
        device="cpu",
        threads=min(os.cpu_count() or 1, MAX_THREADS),
        measured_at=datetime.now(UTC).replace(microsecond=0),
    )
