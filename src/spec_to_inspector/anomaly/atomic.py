"""Directories that either hold a whole result or do not exist."""

import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_directory(final: Path) -> Generator[Path]:
    """Build a directory beside its final place and rename it there on success.

    The block writes into `.<name>.partial` next to `final`. If it ends
    normally, any previous `final` is removed and the partial directory takes
    its name; on any error or interrupt the partial directory is removed and
    a previous `final` is left as it was. A partial directory left behind by a
    killed run is cleared first.

    Args:
        final: The directory to produce.

    Yields:
        The partial directory, empty.
    """
    partial = final.with_name(f".{final.name}.partial")
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    try:
        yield partial
        if final.exists():
            shutil.rmtree(final)
        partial.rename(final)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
