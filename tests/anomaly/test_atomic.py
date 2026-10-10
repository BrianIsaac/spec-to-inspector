"""Tests for building a directory beside its place and swapping it in."""

from pathlib import Path

import pytest

from spec_to_inspector.anomaly import atomic
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
    assert [p.name for p in tmp_path.iterdir()] == ["pcb4"]


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


def test_the_old_directory_is_never_deleted_before_the_new_one_is_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the swap fails, the old directory is put back and the new one is not lost to it."""
    final = tmp_path / "pcb4"
    final.mkdir()
    (final / "old.json").write_text("old")
    real_rename = Path.rename

    def failing_rename(self: Path, target: Path) -> Path:
        if self.name == ".pcb4.partial":
            raise OSError("disk says no")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)

    with pytest.raises(OSError, match="disk says no"), atomic_directory(final) as partial:
        (partial / "new.json").write_text("new")

    assert [p.name for p in tmp_path.iterdir()] == ["pcb4"]
    assert (final / "old.json").read_text() == "old"


def test_removing_the_old_directory_cannot_cost_the_new_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interrupt while the old directory is being removed leaves the new one in place."""
    final = tmp_path / "pcb4"
    final.mkdir()
    (final / "old.json").write_text("old")
    real_rmtree = atomic.shutil.rmtree
    calls: list[str] = []

    def interrupted_rmtree(path: Path, *, ignore_errors: bool = False) -> None:
        calls.append(Path(path).name)
        if Path(path).name == ".pcb4.old":
            raise KeyboardInterrupt
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(atomic.shutil, "rmtree", interrupted_rmtree)

    with pytest.raises(KeyboardInterrupt), atomic_directory(final) as partial:
        (partial / "new.json").write_text("new")

    assert ".pcb4.old" in calls
    assert [p.name for p in final.iterdir()] == ["new.json"]


def test_a_swap_cut_short_by_a_kill_is_recovered(tmp_path: Path) -> None:
    """A backup left with no directory in place is restored; one left beside it is dropped."""
    final = tmp_path / "pcb4"
    backup = tmp_path / ".pcb4.old"
    backup.mkdir()
    (backup / "old.json").write_text("old")

    with pytest.raises(RuntimeError, match="boom"), atomic_directory(final):
        raise RuntimeError("boom")

    assert [p.name for p in tmp_path.iterdir()] == ["pcb4"]
    assert (final / "old.json").read_text() == "old"

    backup.mkdir()
    (backup / "older.json").write_text("older")
    with atomic_directory(final) as partial:
        (partial / "new.json").write_text("new")

    assert [p.name for p in tmp_path.iterdir()] == ["pcb4"]
    assert [p.name for p in final.iterdir()] == ["new.json"]
