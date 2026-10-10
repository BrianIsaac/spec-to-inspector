"""Tests for building a directory beside its place and renaming it in."""

from pathlib import Path

import pytest

from spec_to_inspector.anomaly.atomic import atomic_directory


def test_a_finished_directory_takes_its_place(tmp_path: Path) -> None:
    """What is written in the partial directory appears under the final name."""
    final = tmp_path / "models" / "pcb4"

    with atomic_directory(final) as partial:
        assert partial.parent == final.parent
        assert partial.name.startswith(".")
        assert not final.exists()
        (partial / "model.ckpt").write_bytes(b"weights")

    assert (final / "model.ckpt").read_bytes() == b"weights"
    assert [p.name for p in final.parent.iterdir()] == ["pcb4"]


def test_a_finished_directory_replaces_the_old_one_whole(tmp_path: Path) -> None:
    """Nothing of the previous directory survives beside the new files."""
    final = tmp_path / "pcb4"
    final.mkdir()
    (final / "old.json").write_text("old")

    with atomic_directory(final) as partial:
        (partial / "new.json").write_text("new")

    assert [p.name for p in final.iterdir()] == ["new.json"]


def test_a_failure_leaves_the_old_directory_and_no_partial(tmp_path: Path) -> None:
    """An error inside the block removes the partial directory and keeps what was there."""
    final = tmp_path / "pcb4"
    final.mkdir()
    (final / "old.json").write_text("old")

    with pytest.raises(RuntimeError, match="boom"), atomic_directory(final) as partial:
        (partial / "new.json").write_text("new")
        raise RuntimeError("boom")

    assert [p.name for p in tmp_path.iterdir()] == ["pcb4"]
    assert (final / "old.json").read_text() == "old"


def test_an_interrupt_cleans_up_too(tmp_path: Path) -> None:
    """Ctrl-C inside the block is not swallowed and leaves no partial directory."""
    final = tmp_path / "pcb4"

    with pytest.raises(KeyboardInterrupt), atomic_directory(final):
        raise KeyboardInterrupt

    assert list(tmp_path.iterdir()) == []


def test_a_stale_partial_directory_is_cleared_first(tmp_path: Path) -> None:
    """A partial directory left by a killed run does not leak into the next one."""
    final = tmp_path / "pcb4"
    stale = tmp_path / ".pcb4.partial"
    stale.mkdir()
    (stale / "half.ckpt").write_bytes(b"half")

    with atomic_directory(final) as partial:
        assert partial == stale
        assert list(partial.iterdir()) == []
        (partial / "model.ckpt").write_bytes(b"weights")

    assert [p.name for p in final.iterdir()] == ["model.ckpt"]
