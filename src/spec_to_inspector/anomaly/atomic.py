"""Directories that either hold a whole result or the one before it."""

import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_directory(final: Path) -> Generator[Path]:
    """Build a directory beside its final place and swap it in on success.

    The block writes into `.<name>.partial` next to `final`. If it ends
    normally, a previous `final` is renamed aside to `.<name>.old`, the
    partial directory is renamed into place, and only then is the old one
    removed: at no moment is the old result gone while the new one is not in
    place. On an error or interrupt inside the block the partial directory is
    removed and a previous `final` is left as it was; if the swap itself
    fails, the old directory is put back.

    Leftovers of a killed run are dealt with first: a stale partial directory
    is cleared, and a stale `.old` is restored if nothing is in place, or
    dropped if something is.

    Args:
        final: The directory to produce.

    Yields:
        The partial directory, empty.
    """
    partial = final.with_name(f".{final.name}.partial")
    backup = final.with_name(f".{final.name}.old")
    if backup.exists():
        if final.exists():
            shutil.rmtree(backup)
        else:
            backup.rename(final)
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    try:
        yield partial
        had_previous = final.exists()
        if had_previous:
            final.rename(backup)
        try:
            partial.rename(final)
        except BaseException:
            if had_previous:
                backup.rename(final)
            raise
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    if backup.exists():
        shutil.rmtree(backup)
