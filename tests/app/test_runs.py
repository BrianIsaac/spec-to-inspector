"""Tests for the console's reading of runs, boards and decisions from disk."""

from pathlib import Path

import pytest
from PIL import Image

from spec_to_inspector.app.runs import (
    RunError,
    Status,
    contained,
    count_statuses,
    list_runs,
    open_run,
    source_image,
    unlisted_runs,
)
from tests.app.console_fakes import BATCH, World, write_world
from tests.judge.run_fakes import CATEGORY


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The fake world, written once for the module.

    Returns:
        Where its files are.
    """
    return write_world(tmp_path_factory.mktemp("runs"))


def test_the_runs_directory_lists_each_batch_once(world: World) -> None:
    """A batch is a directory two levels down that holds a run index; nothing else is listed."""
    (world.runs_dir / ".console").mkdir(exist_ok=True)
    (world.runs_dir / CATEGORY / "half-written").mkdir(exist_ok=True)
    (world.runs_dir / "notes.txt").write_text("not a part", encoding="utf-8")

    runs = list_runs(world.runs_dir)

    assert [(run.category, run.name, run.images) for run in runs] == [(CATEGORY, BATCH, 6)]


def test_a_runs_directory_that_does_not_exist_lists_nothing(tmp_path: Path) -> None:
    """A console started before any batch was scored shows none, without failing."""
    assert list_runs(tmp_path / "absent") == []


def test_each_board_carries_its_decision_and_status(world: World) -> None:
    """The boards come back in the run's order, each with the outcome the judge wrote."""
    boards = open_run(world.runs_dir, CATEGORY, BATCH).boards()

    assert [(board.image_id, board.status) for board in boards] == [
        ("good", Status.ACCEPT),
        ("speck", Status.ACCEPT),
        ("scratch", Status.REJECT),
        ("two", Status.REJECT),
        ("peak", Status.NEEDS_REVIEW),
        ("late", Status.NOT_JUDGED),
    ]
    assert boards[-1].decision is None
    assert boards[-1].problem is None
    assert count_statuses(boards) == {
        Status.ACCEPT: 2,
        Status.REJECT: 2,
        Status.NEEDS_REVIEW: 1,
        Status.NOT_JUDGED: 1,
    }


def test_a_decision_that_cannot_be_read_is_said_and_the_board_is_not_judged(
    world: World, tmp_path: Path
) -> None:
    """A damaged decision file does not take the batch page down."""
    damaged = world.run / "late" / "decision.json"
    damaged.write_text("{not json", encoding="utf-8")
    try:
        board = open_run(world.runs_dir, CATEGORY, BATCH).boards()[-1]
    finally:
        damaged.unlink()

    assert board.status is Status.NOT_JUDGED
    assert board.problem is not None
    assert "decision.json" in board.problem


def test_a_board_opens_with_its_result(world: World) -> None:
    """One board's detail holds the anomaly model's sidecar beside the decision."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("scratch")

    assert board.result.image_id == "scratch"
    assert board.directory == world.run / "scratch"
    assert board.decision is not None
    assert board.decision.clause is not None
    assert board.decision.clause.id == "4.1.1"


@pytest.mark.parametrize(
    ("category", "name", "words"),
    [
        (CATEGORY, "absent", "no batch"),
        ("pcb1", BATCH, "no batch"),
        ("..", BATCH, "not a name"),
        (CATEGORY, "../batch", "not a name"),
    ],
)
def test_a_batch_that_is_not_there_is_refused_in_words(
    world: World, category: str, name: str, words: str
) -> None:
    """An unknown batch and a path that climbs out of the runs directory are both refused."""
    with pytest.raises(RunError, match=words):
        open_run(world.runs_dir, category, name)


def test_a_run_filed_under_another_part_is_refused(world: World, tmp_path: Path) -> None:
    """A run whose index names another part than its directory is not shown as that part's."""
    misfiled = tmp_path / "runs" / "pcb1" / BATCH
    misfiled.mkdir(parents=True)
    (misfiled / "run.json").write_text(
        (world.run / "run.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(RunError, match="is a run of part pcb9, not of pcb1"):
        open_run(tmp_path / "runs", "pcb1", BATCH)


def test_a_board_the_run_does_not_hold_is_refused(world: World) -> None:
    """An image id that is not in the run's index is not looked for on disk."""
    run = open_run(world.runs_dir, CATEGORY, BATCH)

    with pytest.raises(RunError, match="holds no board"):
        run.board("absent")
    with pytest.raises(RunError, match="holds no board"):
        run.board("../batch/good")


def test_the_source_image_is_found_where_inference_read_it(world: World) -> None:
    """The photograph is the file inference was given, when it is still there."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("good")

    assert source_image(board.result, data_dir=world.root / "nowhere") == Path(board.result.image)


def test_a_source_image_that_moved_is_looked_for_under_the_data_directory(
    world: World, tmp_path: Path
) -> None:
    """A VisA image recorded by a path relative to another working copy is found by its VisA key."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("good")
    moved = board.result.model_copy(
        update={"image": "elsewhere/000.JPG", "visa_image": "pcb9/Data/Images/Normal/000.JPG"}
    )
    kept = tmp_path / "data" / "visa" / "pcb9" / "Data" / "Images" / "Normal" / "000.JPG"
    kept.parent.mkdir(parents=True)
    Image.new("RGB", (board.result.width, board.result.height)).save(kept, format="JPEG")

    assert source_image(moved, data_dir=tmp_path / "data") == kept
    assert source_image(moved, data_dir=tmp_path / "other") is None


@pytest.mark.parametrize("damage", [b"\xff\xfe\x00 not text", b"", b"\x00" * 64])
def test_a_decision_that_is_not_text_does_not_take_the_batch_down(
    world: World, damage: bytes
) -> None:
    """A decision file cut short, zero-filled or not UTF-8 is a problem on one board, no more."""
    damaged = world.run / "late" / "decision.json"
    damaged.write_bytes(damage)
    try:
        boards = open_run(world.runs_dir, CATEGORY, BATCH).boards()
        detail = open_run(world.runs_dir, CATEGORY, BATCH).board("late")
    finally:
        damaged.unlink()

    assert boards[-1].status is Status.NOT_JUDGED
    assert boards[-1].problem is not None
    assert detail.board.problem is not None


def test_a_file_name_from_a_record_stays_inside_its_directory(tmp_path: Path) -> None:
    """A name read from a result or a decision cannot point outside the board's directory."""
    directory = tmp_path / "run" / "board"
    (directory / "crops").mkdir(parents=True)
    (directory / "crops" / "region-001.png").write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("not the console's to serve", encoding="utf-8")

    assert contained(directory, "crops/region-001.png") == directory / "crops" / "region-001.png"
    assert contained(directory, "../../secret.txt") is None
    assert contained(directory, str(tmp_path / "secret.txt")) is None
    assert contained(directory, "crops/absent.png") is None
    assert contained(directory, None) is None


def test_a_file_of_another_size_is_not_taken_for_the_photograph(
    world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative path that now lands on some other picture is not shown as the board."""
    board = open_run(world.runs_dir, CATEGORY, BATCH).board("good")
    monkeypatch.chdir(tmp_path)
    Image.new("RGB", (64, 48)).save(tmp_path / "board-1.png")
    moved = board.result.model_copy(update={"image": "board-1.png", "visa_image": None})

    assert source_image(moved, data_dir=tmp_path / "data") is None

    Image.new("RGB", (board.result.width, board.result.height)).save(tmp_path / "board-1.png")
    assert source_image(moved, data_dir=tmp_path / "data") == Path("board-1.png")


def test_a_batch_whose_name_cannot_be_served_is_named_not_dropped(
    world: World, tmp_path: Path
) -> None:
    """`inspect --batch "line 3"` makes a run the console cannot link to; it says which."""
    runs = tmp_path / "runs"
    for name in ("line 3", "_scratch", "fine"):
        target = runs / CATEGORY / name
        target.mkdir(parents=True)
        (target / "run.json").write_text(
            (world.run / "run.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
    (runs / ".console").mkdir()

    assert [run.name for run in list_runs(runs)] == ["fine"]
    assert unlisted_runs(runs) == [f"{CATEGORY}/_scratch", f"{CATEGORY}/line 3"]
    assert unlisted_runs(tmp_path / "absent") == []
