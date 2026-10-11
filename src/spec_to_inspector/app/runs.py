"""The batches the console shows: runs on disk, their boards, and each board's decision.

A batch is a run directory the anomaly model wrote,
`<runs-dir>/<part>/<batch>/`, with the judge's `decision.json` beside each
image's result where the board has been judged. Nothing here writes: the
console reads what `train` and `inspect` left.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from PIL import Image

from spec_to_inspector.anomaly.records import ImageResult, RunEntry, RunIndex
from spec_to_inspector.judge.decision import Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import DECISION_NAME, RESULT_NAME, RUN_INDEX_NAME

_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class RunError(LookupError):
    """A batch or a board the console was asked for cannot be shown; the message says why."""


class Status(StrEnum):
    """What the console shows a board as: the judge's outcome, or that there is none yet."""

    ACCEPT = "accept"
    REJECT = "reject"
    NEEDS_REVIEW = "needs-review"
    NOT_JUDGED = "not-judged"

    @property
    def label(self) -> str:
        """The status in words, as the pages print it."""
        return _LABELS[self]

    @classmethod
    def of(cls, decision: Decision | None) -> "Status":
        """Give the status of a board from its decision.

        Args:
            decision: The board's decision, or None if it has not been judged.

        Returns:
            The status.
        """
        if decision is None:
            return cls.NOT_JUDGED
        return _STATUS[decision.outcome]


_LABELS: Final = {
    Status.ACCEPT: "Accept",
    Status.REJECT: "Reject",
    Status.NEEDS_REVIEW: "Needs review",
    Status.NOT_JUDGED: "Not judged",
}
_STATUS: Final = {
    Outcome.ACCEPT: Status.ACCEPT,
    Outcome.REJECT: Status.REJECT,
    Outcome.NEEDS_REVIEW: Status.NEEDS_REVIEW,
}


def is_name(text: str) -> bool:
    """Say whether a text may name a part, a batch or an image in a path.

    Args:
        text: The text, as a request gave it.

    Returns:
        Whether it is letters, digits, dots, dashes and underscores, starting
        with a letter or a digit, so that it cannot climb out of a directory.
    """
    return _NAME.match(text) is not None


@dataclass(frozen=True)
class RunSummary:
    """One batch, as the batch list shows it.

    Attributes:
        category: The part.
        name: The batch's name, its directory's own.
        images: Boards in the batch.
        created_at: When the anomaly model finished scoring it, in UTC, ISO 8601.
    """

    category: str
    name: str
    images: int
    created_at: str


@dataclass(frozen=True)
class Board:
    """One board of a batch, with the judge's decision if it has one.

    Attributes:
        entry: The board's line in the run's index.
        decision: The judge's decision; None if the board has not been judged.
        problem: Why a decision file that is there could not be read; None otherwise.
    """

    entry: RunEntry
    decision: Decision | None
    problem: str | None = None

    @property
    def image_id(self) -> str:
        """The board's name within its batch."""
        return self.entry.image_id

    @property
    def status(self) -> Status:
        """The judge's outcome, or that there is none yet."""
        return Status.of(self.decision)


@dataclass(frozen=True)
class BoardDetail:
    """One board with everything its card draws from.

    Attributes:
        board: The board and its decision.
        directory: The board's directory in the run.
        result: The anomaly model's result for the board.
    """

    board: Board
    directory: Path
    result: ImageResult

    @property
    def decision(self) -> Decision | None:
        """The judge's decision; None if the board has not been judged."""
        return self.board.decision


def _read_decision(directory: Path) -> tuple[Decision | None, str | None]:
    """Read a board's decision, if it has one.

    Args:
        directory: The board's directory in the run.

    Returns:
        The decision and None; or None and None where there is no decision
        file; or None and why the file could not be read.
    """
    path = directory / DECISION_NAME
    try:
        # Read as bytes: a file cut short or zero-filled is then refused by the
        # validation below, in words, like any other file that is not a decision.
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None
    except OSError as error:
        return None, f"{path} could not be read: {error}"
    try:
        return Decision.model_validate_json(data), None
    except ValueError as error:
        first = str(error).splitlines()[0]
        return None, f"{path} is not a decision this console can read: {first}"


@dataclass(frozen=True)
class Run:
    """One batch on disk.

    Attributes:
        category: The part.
        name: The batch's name.
        directory: The run's directory.
        index: The run's index, as the anomaly model wrote it.
    """

    category: str
    name: str
    directory: Path
    index: RunIndex

    def boards(self) -> list[Board]:
        """Read every board of the batch with its decision, in the run's order.

        Returns:
            The boards.
        """
        boards: list[Board] = []
        for entry in self.index.entries:
            decision, problem = _read_decision(self.directory / entry.image_id)
            boards.append(Board(entry=entry, decision=decision, problem=problem))
        return boards

    def board(self, image_id: str) -> BoardDetail:
        """Read one board with its result.

        Args:
            image_id: The board's name within the batch.

        Returns:
            The board, its directory and the anomaly model's result.

        Raises:
            RunError: If the batch holds no such board, or its result cannot be read.
        """
        entry = next((e for e in self.index.entries if e.image_id == image_id), None)
        if entry is None or not is_name(image_id):
            msg = f"batch {self.name} of part {self.category} holds no board {image_id!r}"
            raise RunError(msg)
        directory = self.directory / image_id
        try:
            result = ImageResult.model_validate_json(
                (directory / RESULT_NAME).read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            msg = f"board {image_id} of batch {self.name} has no readable {RESULT_NAME}: {error}"
            raise RunError(msg) from error
        decision, problem = _read_decision(directory)
        return BoardDetail(
            board=Board(entry=entry, decision=decision, problem=problem),
            directory=directory,
            result=result,
        )


def _read_index(directory: Path) -> RunIndex | None:
    """Read a run's index, if the directory is a run.

    Args:
        directory: A directory that may be a run.

    Returns:
        The index, or None if there is none that can be read.
    """
    try:
        return RunIndex.model_validate_json(
            (directory / RUN_INDEX_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def _run_directories(runs_dir: Path) -> list[tuple[Path, RunIndex]]:
    """Find every directory two levels down that holds a readable run index.

    Args:
        runs_dir: The runs directory.

    Returns:
        Each run's directory and index, by part and then by name. A directory
        whose name starts with a dot is the console's own or a run still
        being written, and is passed over.
    """
    if not runs_dir.is_dir():
        return []
    found: list[tuple[Path, RunIndex]] = []
    for part in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        if part.name.startswith("."):
            continue
        for directory in sorted(path for path in part.iterdir() if path.is_dir()):
            if directory.name.startswith("."):
                continue
            index = _read_index(directory)
            if index is not None:
                found.append((directory, index))
    return found


def list_runs(runs_dir: Path) -> list[RunSummary]:
    """List the batches under the runs directory, by part and then by name.

    Args:
        runs_dir: The runs directory.

    Returns:
        One summary per directory two levels down that holds a readable run
        index filed under its own part, and whose part and name the console
        can put in an address; empty if the directory is absent.
    """
    return [
        RunSummary(
            category=directory.parent.name,
            name=directory.name,
            images=len(index.entries),
            created_at=index.created_at,
        )
        for directory, index in _run_directories(runs_dir)
        if is_name(directory.parent.name)
        and is_name(directory.name)
        and index.category == directory.parent.name
    ]


def unlisted_runs(runs_dir: Path) -> list[str]:
    """Name the runs on disk that the console cannot open, because of how they are named.

    `inspect --batch` takes any name; the console puts a batch's name in an
    address and so serves letters, digits, dots, dashes and underscores only.

    Args:
        runs_dir: The runs directory.

    Returns:
        Each such run as "<part>/<batch>", in order.
    """
    return [
        f"{directory.parent.name}/{directory.name}"
        for directory, _ in _run_directories(runs_dir)
        if not (is_name(directory.parent.name) and is_name(directory.name))
    ]


def open_run(runs_dir: Path, category: str, name: str) -> Run:
    """Open one batch.

    Args:
        runs_dir: The runs directory.
        category: The part.
        name: The batch's name.

    Returns:
        The batch.

    Raises:
        RunError: If either name could climb out of the runs directory, there
            is no such batch, or the run there belongs to another part.
    """
    for text in (category, name):
        if not is_name(text):
            msg = f"{text!r} is not a name of a part or a batch"
            raise RunError(msg)
    directory = runs_dir / category / name
    index = _read_index(directory)
    if index is None:
        msg = f"there is no batch {name} of part {category} under {runs_dir}"
        raise RunError(msg)
    if index.category != category:
        msg = f"{directory} is a run of part {index.category}, not of {category}"
        raise RunError(msg)
    return Run(category=category, name=name, directory=directory, index=index)


def count_statuses(boards: Sequence[Board]) -> dict[Status, int]:
    """Count a batch's boards by status.

    Args:
        boards: The boards.

    Returns:
        How many boards have each status, every status present.
    """
    counts = dict.fromkeys(Status, 0)
    for board in boards:
        counts[board.status] += 1
    return counts


def contained(directory: Path, name: str | None) -> Path | None:
    """Resolve a file name read from a record, if it stays inside its directory.

    A result or a decision names its own files (a crop, an overlay, the
    anomaly map). The console serves them, so a name that climbs out of the
    board's directory, or is absolute, is not followed.

    Args:
        directory: The board's directory in the run.
        name: The file's name as the record gives it, relative to the directory.

    Returns:
        The file's path, or None if there is no name, the file is not there,
        or it lies outside the directory.
    """
    if name is None:
        return None
    path = directory / name
    try:
        inside = path.resolve().is_relative_to(directory.resolve())
    except OSError:
        return None
    return path if inside and path.is_file() else None


def _is_photograph_of(path: Path, result: ImageResult) -> bool:
    """Say whether a file is a picture of the size the result was scored from.

    Args:
        path: A candidate file.
        result: The anomaly model's result for the board.

    Returns:
        Whether the file opens as an image of the result's width and height.
    """
    try:
        with Image.open(path) as opened:
            return opened.size == (result.width, result.height)
    except (OSError, ValueError):
        return False


def source_image(result: ImageResult, *, data_dir: Path) -> Path | None:
    """Find the photograph a result was scored from.

    The result records the path inference was given, which may be relative
    to another working directory; a file found there is taken for the
    photograph only if it has the photograph's size, so that some other
    picture of the same name is not shown as the board.

    Args:
        result: The anomaly model's result for the board.
        data_dir: The settings' data directory, where VisA is kept.

    Returns:
        The file inference was given if it is still there; else the same VisA
        image under the data directory; else None.
    """
    recorded = Path(result.image)
    if _is_photograph_of(recorded, result):
        return recorded
    if result.visa_image is not None:
        kept = data_dir / "visa" / result.visa_image
        if _is_photograph_of(kept, result):
            return kept
    return None
