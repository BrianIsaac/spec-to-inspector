"""The PDF reader: docling turns a specification's PDF into blocks.

docling's standard PDF pipeline runs on the CPU (the card is kept for the
anomaly model and the judge), without OCR (the specification is born
digital), with table structure on and with heading levels on
(`HeadingHierarchyOptions(enabled=True)`), so `5`, `5.6` and the title do not
all arrive at level 1. Levels come from the PDF's outline where it has one
and from the numbering otherwise.

docling's layout and table models (530 MB) are fetched on first use into the
Hugging Face cache, shared by every checkout on the machine; a machine with
no network is given them in a directory and pointed at it with
`SPEC_TO_INSPECTOR_DOCLING_ARTIFACTS_DIR` (`docling-tools models download -o
<dir>` fills one).
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.spec.blocks import Block, Heading, Paragraph, Table
from spec_to_inspector.spec.extract import extract_specification
from spec_to_inspector.spec.schema import Specification

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

MAX_THREADS: Final = 8

# What docling labels a page's furniture and a figure's caption: printed, but not the
# document's running text.
_NOT_TEXT: Final = frozenset({"caption", "footnote", "page_header", "page_footer"})

_CONVERTERS: Final[dict[Path | None, "DocumentConverter"]] = {}


class PdfError(RuntimeError):
    """A PDF could not be read into blocks."""


class ParsedPdf(BaseModel):
    """A PDF as docling read it.

    Attributes:
        blocks: The headings, paragraphs and tables in reading order.
        pages: The number of pages.
        text: The document as Markdown text: what a language model is given
            when it is given the whole specification.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    blocks: tuple[Block, ...]
    pages: int
    text: str

    def specification(self) -> Specification:
        """Extract the specification from the blocks.

        Returns:
            The validated specification.

        Raises:
            SpecificationError: If the document does not have a
                specification's structure.
        """
        return extract_specification(self.blocks, pages=self.pages)


def _converter(artifacts_dir: Path | None) -> "DocumentConverter":
    """Build docling's converter for born-digital PDFs, once per models directory.

    The converter holds the layout and table models, so a process that parses
    more than one document loads them once.

    Args:
        artifacts_dir: A directory holding docling's models, or None for the
            Hugging Face cache.

    Returns:
        The converter.
    """
    if artifacts_dir not in _CONVERTERS:
        # Imported here: docling pulls in torch, and the command line should start without it.
        from docling.datamodel.accelerator_options import (  # noqa: PLC0415
            AcceleratorDevice,
            AcceleratorOptions,
        )
        from docling.datamodel.base_models import InputFormat  # noqa: PLC0415
        from docling.datamodel.pipeline_options import (  # noqa: PLC0415
            HeadingHierarchyOptions,
            PdfPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption  # noqa: PLC0415

        options = PdfPipelineOptions(
            artifacts_path=artifacts_dir,
            do_ocr=False,
            do_table_structure=True,
            heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),
            accelerator_options=AcceleratorOptions(
                device=AcceleratorDevice.CPU, num_threads=min(os.cpu_count() or 1, MAX_THREADS)
            ),
        )
        _CONVERTERS[artifacts_dir] = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
    return _CONVERTERS[artifacts_dir]


def read_pdf(path: Path, *, artifacts_dir: Path | None = None) -> ParsedPdf:
    """Read a born-digital PDF into blocks with docling, on the CPU.

    Args:
        path: The PDF.
        artifacts_dir: A directory holding docling's models, for a machine
            without network; by default they are fetched into the Hugging
            Face cache on first use.

    Returns:
        The PDF's blocks, page count and Markdown text.

    Raises:
        PdfError: If the file is missing or docling cannot convert it.
    """
    if not path.is_file():
        raise PdfError(f"{path} is not a file")
    from docling_core.types.doc.items.table.table import TableItem  # noqa: PLC0415
    from docling_core.types.doc.items.text import SectionHeaderItem, TextItem  # noqa: PLC0415

    try:
        document = _converter(artifacts_dir).convert(path).document
    except Exception as error:
        raise PdfError(f"docling could not convert {path}: {error}") from error

    blocks: list[Block] = []
    for item, _ in document.iterate_items():
        if isinstance(item, TableItem):
            rows = tuple(tuple(cell.text for cell in row) for row in item.data.grid)
            blocks.append(Table(rows=rows, page=item.prov[0].page_no))
        elif isinstance(item, SectionHeaderItem):
            # `orig` is the heading as printed; `text` loses the number of a heading that
            # docling first took for a list item and then promoted from the outline.
            blocks.append(Heading(level=item.level, text=item.orig, page=item.prov[0].page_no))
        elif isinstance(item, TextItem) and item.label.value not in _NOT_TEXT and item.text:
            blocks.append(Paragraph(text=item.text, page=item.prov[0].page_no))
    return ParsedPdf(
        blocks=tuple(blocks), pages=len(document.pages), text=document.export_to_markdown()
    )
