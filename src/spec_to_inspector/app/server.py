"""The console as the `serve` verb builds it: from the settings, with the real parser."""

from pathlib import Path
from typing import Final

from fastapi import FastAPI

from spec_to_inspector.app.sink import CorrectionSink
from spec_to_inspector.app.specs import SpecStore, docling_parser
from spec_to_inspector.app.web import ConsoleConfig, create_app
from spec_to_inspector.settings import Settings

LOOPBACK: Final = frozenset({"127.0.0.1", "localhost"})
STATE_DIR_NAME: Final = ".console"
"""The console's own directory under the runs directory; the batch list skips it."""


def default_state_dir(settings: Settings) -> Path:
    """Give where the console keeps its uploaded specification and its training logs.

    Args:
        settings: The settings.

    Returns:
        `.console` under the runs directory.
    """
    return settings.runs_dir / STATE_DIR_NAME


def answered_hosts(host: str | None) -> tuple[str, ...]:
    """Give the host names a console bound to an address should answer to.

    Args:
        host: The address `serve` listens on, or None where the console is
            not served on a socket.

    Returns:
        This machine's two loopback names for a loopback address; the
        address itself for another IPv4 address or a name; nothing, meaning
        any name, for all interfaces and for IPv6 addresses, whose `Host`
        header the check does not parse.
    """
    if host in LOOPBACK:
        return ("127.0.0.1", "localhost")
    if host is None or host == "0.0.0.0" or ":" in host:  # noqa: S104 - compared, not bound
        return ()
    return (host,)


def build_console(
    settings: Settings,
    *,
    state_dir: Path | None = None,
    spec: Path | None = None,
    sink: CorrectionSink | None = None,
    host: str | None = None,
) -> FastAPI:
    """Build the console over the settings' directories.

    Args:
        settings: Where the runs, the models and the data are, and docling's models.
        state_dir: The console's own directory; `.console` under the runs
            directory by default.
        spec: A clause table `parse` wrote, to start with; by default the
            last specification uploaded to the console, if any.
        sink: Where the override form records. None keeps overrides in
            memory; the corrections store is joined by passing it here.
        host: The address the console will listen on, which decides the host
            names it answers to; None to answer to any.

    Returns:
        The application.

    Raises:
        SpecError: If `spec` is given and cannot be read as a clause table.
    """
    state = state_dir if state_dir is not None else default_state_dir(settings)
    return create_app(
        ConsoleConfig(
            runs_dir=settings.runs_dir,
            models_dir=settings.models_dir,
            data_dir=settings.data_dir,
            state_dir=state,
            hosts=answered_hosts(host),
        ),
        specs=SpecStore(state, parser=docling_parser(settings.docling_artifacts_dir), initial=spec),
        sink=sink,
    )
