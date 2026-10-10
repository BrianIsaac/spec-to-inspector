"""The specification the console holds: uploaded as a PDF, parsed, kept, and shown.

One specification is in force at a time. An upload is parsed before it
replaces anything, so a PDF that does not parse leaves the earlier one in
force. What is in force is kept in the console's state directory (the PDF,
its clause table as `parse` writes it, and a note of where it came from), so
a restart does not lose it and `inspect --spec` can be pointed at the table.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Final

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.spec.extract import SpecificationError
from spec_to_inspector.spec.pdf import PdfError, read_pdf
from spec_to_inspector.spec.schema import Specification, read_clause_table, write_clause_table

PDF_NAME: Final = "specification.pdf"
TABLE_NAME: Final = "specification.clauses.json"
NOTE_NAME: Final = "specification.json"
TABLE_SUFFIX: Final = ".clauses.json"
MAX_UPLOAD_BYTES: Final = 64 * 1024 * 1024

Parser = Callable[[Path], Specification]
"""Reads a PDF into a specification; raises `PdfError` or `SpecificationError` in words."""


class SpecError(RuntimeError):
    """A specification could not be taken into force; the message is fit to show."""


class _Note(BaseModel):
    """Where the kept specification came from.

    Attributes:
        source: The uploaded file's name.
        parse_seconds: How long the parse took.
        loaded_at: When it was taken into force, in UTC, ISO 8601.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    parse_seconds: float | None
    loaded_at: str


class LoadedSpec(BaseModel):
    """The specification in force.

    Attributes:
        specification: The clause table, with its zones and calibrations.
        pdf: The PDF to draw pages from; None if only a clause table was given.
        table: The clause table's file, as `inspect --spec` reads it.
        source: The uploaded file's name, or the path given at start.
        parse_seconds: How long the upload took to parse; None for a table
            given at start, which was parsed elsewhere.
        loaded_at: When it was taken into force, in UTC, ISO 8601.
    """

    model_config = ConfigDict(frozen=True)

    specification: Specification
    pdf: Path | None
    table: Path
    source: str
    parse_seconds: float | None
    loaded_at: str


def docling_parser(artifacts_dir: Path | None) -> Parser:
    """Give the console's own parser: docling on the CPU, then the clause extractor.

    Args:
        artifacts_dir: A directory holding docling's models, or None for the
            Hugging Face cache.

    Returns:
        The parser.
    """

    def parse(path: Path) -> Specification:
        return read_pdf(path, artifacts_dir=artifacts_dir).specification()

    return parse


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SpecStore:
    """Holds the specification in force and takes uploads.

    Attributes:
        parser: Reads an uploaded PDF into a specification.
    """

    def __init__(self, state_dir: Path, *, parser: Parser, initial: Path | None = None) -> None:
        """Start with the table named, else with the last upload kept, else with nothing.

        Args:
            state_dir: The console's state directory; made on first upload.
            parser: Reads an uploaded PDF into a specification.
            initial: A clause table `parse` wrote, to start with; the PDF of
                the same name beside it is shown with it.

        Raises:
            SpecError: If `initial` is given and cannot be read as a clause table.
        """
        self.parser = parser
        self._state_dir = state_dir
        self._lock = Lock()
        self._installing = Lock()
        self._current = self._read_initial(initial) if initial is not None else self._read_kept()

    @staticmethod
    def _read_initial(table: Path) -> LoadedSpec:
        try:
            specification = read_clause_table(table)
        except OSError as error:
            msg = f"cannot read the specification {table}: {error}"
            raise SpecError(msg) from error
        except ValueError as error:
            msg = f"{table} is not a valid clause table: {error}"
            raise SpecError(msg) from error
        stem = table.name.removesuffix(TABLE_SUFFIX) if table.name.endswith(TABLE_SUFFIX) else None
        pdf = table.with_name(f"{stem}.pdf") if stem else None
        return LoadedSpec(
            specification=specification,
            pdf=pdf if pdf is not None and pdf.is_file() else None,
            table=table,
            source=str(table),
            parse_seconds=None,
            loaded_at=_now(),
        )

    def _read_kept(self) -> LoadedSpec | None:
        table = self._state_dir / TABLE_NAME
        try:
            specification = read_clause_table(table)
            note = _Note.model_validate_json(
                (self._state_dir / NOTE_NAME).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None
        pdf = self._state_dir / PDF_NAME
        return LoadedSpec(
            specification=specification,
            pdf=pdf if pdf.is_file() else None,
            table=table,
            source=note.source,
            parse_seconds=note.parse_seconds,
            loaded_at=note.loaded_at,
        )

    def current(self) -> LoadedSpec | None:
        """Give the specification in force.

        Returns:
            The specification, or None if none has been loaded.
        """
        with self._lock:
            return self._current

    def install(self, filename: str, data: bytes) -> LoadedSpec:
        """Parse an uploaded PDF and, if it parses, take it into force.

        Args:
            filename: The file's name as the browser gave it.
            data: The file's bytes.

        Returns:
            The specification now in force.

        Raises:
            SpecError: If nothing was uploaded, the file is not a PDF, or it
                does not parse into a specification; what was in force stays.
        """
        name = Path(filename).name
        if not name:
            raise SpecError("no file was chosen: pick the specification's PDF first")
        if not data:
            msg = f"{name} is empty"
            raise SpecError(msg)
        if len(data) > MAX_UPLOAD_BYTES:
            msg = f"{name} is {len(data) / 1e6:.0f} MB; the console takes a PDF of up to 64 MB"
            raise SpecError(msg)
        if not data.lstrip().startswith(b"%PDF-"):
            msg = f"{name} is not a PDF: it does not begin with a PDF header"
            raise SpecError(msg)

        # One upload at a time; the parse, which takes seconds, is not done under the lock
        # that every page takes to read what is in force.
        with self._installing:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            partial = self._state_dir / f".{PDF_NAME}.partial"
            partial.write_bytes(data)
            started = time.perf_counter()
            try:
                specification = self.parser(partial)
            except (PdfError, SpecificationError) as error:
                partial.unlink(missing_ok=True)
                # The parser names the temporary file it was given; the engineer knows it
                # by the name they uploaded.
                raise SpecError(str(error).replace(str(partial), name)) from error
            seconds = time.perf_counter() - started

            note = _Note(source=name, parse_seconds=seconds, loaded_at=_now())
            table = self._state_dir / TABLE_NAME
            pdf = self._state_dir / PDF_NAME
            new_table = self._state_dir / f".{TABLE_NAME}.partial"
            new_note = self._state_dir / f".{NOTE_NAME}.partial"
            try:
                # Each file is written whole beside its place and renamed in, so a disk
                # that fails part of the way leaves what was kept before as it was.
                write_clause_table(specification, new_table)
                new_note.write_text(note.model_dump_json(indent=2) + "\n", encoding="utf-8")
                new_table.replace(table)
                partial.replace(pdf)
                new_note.replace(self._state_dir / NOTE_NAME)
            except OSError as error:
                for left in (partial, new_table, new_note):
                    left.unlink(missing_ok=True)
                msg = f"{name} was parsed, but could not be kept in {self._state_dir}: {error}"
                raise SpecError(msg) from error
            loaded = LoadedSpec(
                specification=specification,
                pdf=pdf,
                table=table,
                source=note.source,
                parse_seconds=note.parse_seconds,
                loaded_at=note.loaded_at,
            )
            with self._lock:
                self._current = loaded
            return loaded
