"""The one entry point: `spec-to-inspector <verb>`."""

from typing import NoReturn

import typer
from rich.console import Console

app = typer.Typer(
    name="spec-to-inspector",
    help="Turn a PCB workmanship specification into a visual inspector that cites its clauses.",
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(help="Fetch and verify the VisA PCB data.", no_args_is_help=True)
app.add_typer(data_app, name="data")

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


@data_app.command("fetch")
def data_fetch() -> None:
    """Stream VisA, keep the four PCB categories, and verify the published counts."""
    _not_built("data fetch", "U1")


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
