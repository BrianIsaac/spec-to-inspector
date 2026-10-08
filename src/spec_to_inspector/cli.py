"""The one entry point: `spec-to-inspector <verb>`."""

import signal
from collections.abc import Generator
from contextlib import contextmanager
from types import FrameType
from typing import Annotated, NoReturn

import typer
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
            )
            self._next_tenth += 1


def _counts_table(result: FetchResult) -> Table:
    """Lay out the verified counts per category.

    Args:
        result: The fetch's result.

    Returns:
        A table with one row per category.
    """
    table = Table(title=f"VisA, verified against the published counts ({result.path})")
    for column in ("Category", "Normal", "Anomalous", "Train", "Test normal", "Multi-defect"):
        table.add_column(column, justify="left" if column == "Category" else "right")
    table.add_column("Defect types (images)")
    for name, counts in result.manifest.categories.items():
        table.add_row(
            name,
            str(counts.normal),
            str(counts.anomalous),
            str(counts.train_normal),
            str(counts.test_normal),
            str(counts.multi_defect),
            ", ".join(f"{kind} {n}" for kind, n in counts.defect_types.items()),
        )
    return table


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
        err.print(f"Streaming {settings.visa_url} through tar into {dest}")
    else:
        err.print(f"Re-verifying {dest} against its manifest")
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
        err.print(str(error), markup=False, highlight=False)
        raise typer.Exit(code=1) from error

    out.print(_counts_table(result))
    source, tree = result.manifest.source, result.manifest.tree
    verb = "Streamed" if result.downloaded else "Re-verified"
    out.print(
        f"{verb}: {tree.files} files, {tree.bytes / 1024**2:.0f} MiB kept from "
        f"{source.bytes:,} bytes (sha256 {source.sha256}).",
        markup=False,
        highlight=False,
    )
    out.print(f"Manifest: {dest / MANIFEST_NAME}", markup=False, highlight=False)


@app.command()
def parse() -> None:
    """Parse a specification PDF into its clause table."""
    _not_built("parse", "U3")


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
