"""The one entry point: `spec-to-inspector <verb>`."""

import signal
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Annotated, NoReturn

import typer
from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from spec_to_inspector.datasets.visa import (
    MANIFEST_NAME,
    FetchResult,
    VisaFetchError,
    VisaVerificationError,
    fetch_visa,
)
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.extract import SpecificationError
from spec_to_inspector.spec.limits import Comparison
from spec_to_inspector.spec.pdf import PdfError, read_pdf
from spec_to_inspector.spec.schema import Specification, write_clause_table
from spec_to_inspector.spec.summary import summarise
from spec_to_inspector.spec.tokens import TokenizerError

app = typer.Typer(
    name="spec-to-inspector",
    help="Turn a PCB workmanship specification into a visual inspector that cites its clauses.",
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(help="Fetch and verify the VisA PCB data.", no_args_is_help=True)
app.add_typer(data_app, name="data")

out = Console()
err = Console(stderr=True)


def _not_built(verb: str, unit: str) -> NoReturn:
    """Report that a verb is a stub and exit non-zero.

    Args:
        verb: The verb invoked.
        unit: The Stage I unit that builds it.

    Raises:
        typer.Exit: Always, with code 1.
    """
    err.print(f"spec-to-inspector {verb}: not built yet; unit {unit} builds it.")
    raise typer.Exit(code=1)


@contextmanager
def _terminate_cleanly() -> Generator[None]:
    """Turn SIGTERM into SystemExit for the duration, so cleanup code runs on a kill.

    Yields:
        Nothing; the previous handler is restored on exit.
    """

    def _exit(signum: int, frame: FrameType | None) -> NoReturn:
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, _exit)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


class _ProgressReport:
    """Progress of a stream: a live bar on a terminal, a plain line per tenth elsewhere."""

    def __init__(self, progress: Progress, task: TaskID, console: Console) -> None:
        """Bind the report to its bar and console.

        Args:
            progress: The live bar, shown only on a terminal.
            task: The bar's task.
            console: Where plain lines go when there is no terminal.
        """
        self._progress = progress
        self._task = task
        self._console = console
        self._next_tenth = 1

    def __call__(self, done: int, total: int | None) -> None:
        """Record the bytes received so far.

        Args:
            done: Bytes received.
            total: The stream's size, if known.
        """
        self._progress.update(self._task, completed=done, total=total)
        if self._console.is_terminal or not total:
            return
        while self._next_tenth <= 10 and done * 10 >= total * self._next_tenth:
            self._console.print(
                f"Received {done / 1e6:,.0f} of {total / 1e6:,.0f} MB ({self._next_tenth * 10}%)",
                markup=False,
                highlight=False,
                soft_wrap=True,
            )
            self._next_tenth += 1


def _counts_table(result: FetchResult) -> Table:
    """Lay out the verified counts per category, narrow enough for an 80-column log.

    Args:
        result: The fetch's result.

    Returns:
        A table with one row per category.
    """
    table = Table(
        title=f"VisA, verified against the published counts ({result.path})",
        box=box.SIMPLE_HEAD,
    )
    table.add_column("Category")
    for column in (
        "Normal",
        "Anomalous",
        "Masks",
        "Train",
        "Test\nnormal",
        "Test\nanomalous",
        "Multi-\ndefect",
    ):
        table.add_column(column, justify="right")
    for name, counts in result.manifest.categories.items():
        table.add_row(
            name,
            *(
                str(n)
                for n in (
                    counts.normal,
                    counts.anomalous,
                    counts.masks,
                    counts.train_normal,
                    counts.test_normal,
                    counts.test_anomalous,
                    counts.multi_defect,
                )
            ),
        )
    return table


def _defect_lines(result: FetchResult) -> list[str]:
    """List each category's defect types with their image counts, most common first.

    Args:
        result: The fetch's result.

    Returns:
        One line per category.
    """
    return [
        f"{name} defect types: "
        + ", ".join(f"{kind} {n}" for kind, n in counts.defect_types.items())
        for name, counts in result.manifest.categories.items()
    ]


@data_app.command("fetch")
def data_fetch(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Stream afresh even if a manifest is present; replaces everything under "
            "the dataset directory, Anomalib's split copy included.",
        ),
    ] = False,
) -> None:
    """Stream VisA through tar, keep the four PCB categories, and verify the published counts.

    The tarball is never stored. With a manifest already present, nothing is
    downloaded: the kept files are recounted and rehashed instead.
    """
    settings = Settings()
    dest = settings.visa_dir
    streaming = force or not (dest / MANIFEST_NAME).is_file()
    if streaming:
        err.print(f"Streaming {settings.visa_url} through tar into {dest}", soft_wrap=True)
    else:
        err.print(f"Re-verifying {dest} against its manifest", soft_wrap=True)
    progress = Progress(
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=err,
        disable=not streaming,
    )
    report = _ProgressReport(progress, progress.add_task("VisA", total=None), err)
    try:
        with _terminate_cleanly(), progress:
            result = fetch_visa(
                dest,
                url=settings.visa_url,
                force=force,
                on_progress=report,
            )
    except (VisaFetchError, VisaVerificationError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error

    out.print(_counts_table(result))
    for line in _defect_lines(result):
        out.print(line, markup=False, highlight=False, soft_wrap=True)
    source, tree = result.manifest.source, result.manifest.tree
    verb = "Streamed" if result.downloaded else "Re-verified"
    out.print(
        f"{verb}: {tree.files} files, {tree.bytes / 1024**2:.0f} MiB kept from "
        f"{source.bytes:,} bytes (sha256 {source.sha256}).",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    out.print(f"Manifest: {dest / MANIFEST_NAME}", markup=False, highlight=False, soft_wrap=True)


def _clause_table(specification: Specification) -> Table:
    """Lay out the clause table, one row per clause.

    Args:
        specification: The parsed specification.

    Returns:
        A table of every clause with its part, class, zone, limit, disposition and page.
    """
    table = Table(title=specification.title, box=box.SIMPLE_HEAD)
    for column in ("Clause", "Title", "Part", "Defect class", "Zone", "Limit", "Disposition"):
        table.add_column(column)
    table.add_column("Page", justify="right")
    for clause in specification.clauses:
        limit = (
            "any size"
            if clause.comparison is Comparison.UNCONDITIONAL
            else f"{clause.comparison.value} {clause.limit:g} {clause.unit}"
        )
        table.add_row(
            clause.id,
            clause.title,
            clause.category,
            clause.defect_class,
            clause.zone,
            limit,
            clause.disposition.value,
            str(clause.page),
        )
    return table


@app.command()
def parse(
    pdf: Annotated[Path, typer.Argument(help="The specification, a born-digital PDF.")],
    out_path: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Where the clause table goes; beside the PDF, as <name>.clauses.json, by default.",
        ),
    ] = None,
    results: Annotated[
        Path | None,
        typer.Option(
            "--results",
            help="Also write the measured summary (pages, clauses, tokens, parse time) "
            "to this JSON file.",
        ),
    ] = None,
) -> None:
    """Parse a specification PDF into its clause table.

    docling reads the PDF on the CPU with heading levels on; the clauses,
    zones and calibrations are extracted, validated and written as JSON; a
    summary line gives the pages, the clauses and the document's size in the
    judge's tokens.
    """
    settings = Settings()
    started = time.perf_counter()
    try:
        parsed = read_pdf(pdf, artifacts_dir=settings.docling_artifacts_dir)
        specification = parsed.specification()
    except (PdfError, SpecificationError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error
    seconds = time.perf_counter() - started
    target = out_path if out_path is not None else pdf.with_suffix(".clauses.json")
    write_clause_table(specification, target)

    out.print(_clause_table(specification))
    headings = len({clause.heading_id for clause in specification.clauses})
    counted = f"{specification.pages} pages, {len(specification.clauses)} clauses under "
    counted += f"{headings} numbered headings"
    try:
        summary = summarise(pdf, parsed, specification, parse_seconds=seconds)
    except TokenizerError as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        summary = None
    tokens = (
        f"{summary.document_tokens:,} tokens ({summary.tokenizer})"
        if summary is not None
        else "tokens not counted"
    )
    out.print(
        f"Parsed {pdf}: {counted}, {tokens}, {seconds:.1f} s on the CPU.",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    out.print(f"Clause table: {target}", markup=False, highlight=False, soft_wrap=True)
    if results is not None:
        if summary is None:
            err.print(f"The summary was not written to {results}: tokens could not be counted.")
            raise typer.Exit(code=1)
        summary.write(results)
        out.print(f"Summary: {results}", markup=False, highlight=False, soft_wrap=True)


@app.command()
def train() -> None:
    """Train the anomaly model on good boards of one category."""
    _not_built("train", "U2")


@app.command()
def inspect() -> None:
    """Inspect a batch of board images and judge each region against the clauses."""
    _not_built("inspect", "U5")


@app.command()
def bench() -> None:
    """Run the pipeline on the labelled set and write the measured figures."""
    _not_built("bench", "U7")


@app.command()
def serve() -> None:
    """Serve the local inspection console."""
    _not_built("serve", "U8")
