"""The corrections store: the engineer's overrides, kept in one SQLite file.

An override is one row: which region of which board, what the judge said of
it, what the engineer corrected that to, the engineer's note and the time.
The file lives under the runs directory, so it is copied with the runs. Every
call opens the file, does its work and closes it, so the console and the
command line can write the same store, and a store whose file does not exist
is simply empty: reading never creates it.

Recall gives the corrections the judge is shown, most recent first and at
most three: by part, or by part with the class and the clause the judge named
then. Where a region was overridden more than once, only the engineer's last
word on it is recalled; the earlier rows stay as history.
"""

import sqlite3
from collections.abc import Generator, Sequence
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from spec_to_inspector.judge.disposition import Outcome

STORE_SCHEMA_VERSION: Final = 1
MAX_RECALL: Final = 3
MAX_NOTE_CHARACTERS: Final = 300
_BUSY_SECONDS: Final = 10.0

_Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_ClassName = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z]+( [A-Za-z]+)*$")
]
_ClauseNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]+(\.[0-9]+)*$")
]

_CREATE: Final = """
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    image_id TEXT NOT NULL,
    region_index INTEGER NOT NULL CHECK (region_index >= 1),
    crop_path TEXT,
    judged_class TEXT,
    judged_clause TEXT,
    judged_outcome TEXT NOT NULL,
    judged_reason TEXT,
    corrected_class TEXT,
    corrected_clause TEXT,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX corrections_by_region ON corrections (category, image_id, region_index, id);
"""

_COLUMNS: Final = (
    "category",
    "image_id",
    "region_index",
    "crop_path",
    "judged_class",
    "judged_clause",
    "judged_outcome",
    "judged_reason",
    "corrected_class",
    "corrected_clause",
    "note",
)

# The engineer's last word on a region: the row with the highest id among those of the region.
_LATEST: Final = """
SELECT * FROM corrections AS kept
WHERE kept.category = ?
  AND kept.id = (
      SELECT MAX(other.id) FROM corrections AS other
      WHERE other.category = kept.category
        AND other.image_id = kept.image_id
        AND other.region_index = kept.region_index
  )
"""


class StoreError(RuntimeError):
    """The corrections file cannot be used as a store; the message says why."""


class Override(BaseModel):
    """An engineer's override of the judge on one region of one board.

    Attributes:
        category: The part the board is.
        image_id: The image's name within its run.
        region_index: The region's index in the anomaly model's result, from 1.
        crop_path: The crop the judge was shown, as a path; None if it had none.
        judged_class: The defect class the judge named; None if it named none.
        judged_clause: The numbered heading the judge cited; None with the class.
        judged_outcome: What the region's decision was: accept, reject or
            needs review.
        judged_reason: The judge's own line of description; None when no valid
            answer came, which is how "no clause applies" is told from silence.
        corrected_class: The class the engineer says it is; None when the
            engineer says no clause applies.
        corrected_clause: The numbered heading the engineer cites; None with
            the class.
        note: The engineer's note, folded to one line; may be empty.
    """

    model_config = ConfigDict(frozen=True)

    category: _Name
    image_id: _Name
    region_index: int = Field(ge=1)
    crop_path: str | None = None
    judged_class: _ClassName | None = None
    judged_clause: _ClauseNumber | None = None
    judged_outcome: Outcome
    judged_reason: str | None = None
    corrected_class: _ClassName | None = None
    corrected_clause: _ClauseNumber | None = None
    note: Annotated[str, StringConstraints(max_length=MAX_NOTE_CHARACTERS)] = ""

    @field_validator("note", mode="before")
    @classmethod
    def _one_line(cls, value: object) -> object:
        """Fold the note's line breaks and runs of spaces.

        Args:
            value: The note as given.

        Returns:
            The note on one line, or the value unchanged if it is not text.
        """
        return " ".join(value.split()) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _a_correction(self) -> Self:
        """Refuse half a citation, and an override that changes nothing.

        Returns:
            The override unchanged.

        Raises:
            ValueError: If a class is given without its clause or the reverse,
                or the engineer's answer is the judge's own.
        """
        if (self.judged_class is None) != (self.judged_clause is None):
            msg = "the judged class and clause must both be given or both be null: both or neither"
            raise ValueError(msg)
        if (self.corrected_class is None) != (self.corrected_clause is None):
            msg = (
                "the corrected class and clause must both be given or both be null: both or neither"
            )
            raise ValueError(msg)
        same = (self.judged_class, self.judged_clause) == (
            self.corrected_class,
            self.corrected_clause,
        )
        if same and self.judged_reason is not None:
            msg = "the override repeats the judge's own answer, so there is nothing to correct"
            raise ValueError(msg)
        return self


class Correction(Override):
    """An override as the store holds it.

    Attributes:
        id: The row's number; a later override has a higher one.
        created_at: When it was recorded, in UTC, ISO 8601.
    """

    id: int = Field(ge=1)
    created_at: str


class CorrectionStore:
    """The engineer's overrides in one SQLite file.

    Attributes:
        path: The file; absent until the first override is recorded.
    """

    def __init__(self, path: Path) -> None:
        """Name the store's file, without touching it.

        Args:
            path: The SQLite file.
        """
        self.path = path

    @contextmanager
    def _open(self, *, create: bool) -> Generator[sqlite3.Connection]:
        """Open the file for one piece of work, in one transaction.

        Args:
            create: Whether to make the file's directory and its table if
                they are missing.

        Yields:
            The connection.

        Raises:
            StoreError: If the file is not a corrections store of this layout,
                or cannot be opened.
        """
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(self.path, timeout=_BUSY_SECONDS)) as connection:
                connection.row_factory = sqlite3.Row
                with connection:
                    self._migrate(connection, create=create)
                    yield connection
        except sqlite3.OperationalError as error:
            msg = f"the corrections store {self.path} cannot be used: {error}"
            raise StoreError(msg) from error
        except sqlite3.DatabaseError as error:
            msg = f"{self.path} is not a corrections store: {error}"
            raise StoreError(msg) from error

    def _migrate(self, connection: sqlite3.Connection, *, create: bool) -> None:
        """Make the table in a new file, and refuse a file of another layout.

        Args:
            connection: The open file.
            create: Whether an empty file may be given the table.

        Raises:
            StoreError: If the file holds another layout than this code writes.
        """
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
        if version == 0 and tables == 0:
            if create:
                connection.executescript(
                    f"BEGIN;{_CREATE}PRAGMA user_version = {STORE_SCHEMA_VERSION};COMMIT;"
                )
            return
        if version != STORE_SCHEMA_VERSION:
            msg = (
                f"{self.path} is a corrections store of layout {version}; this code reads "
                f"layout {STORE_SCHEMA_VERSION}"
            )
            raise StoreError(msg)

    def record(self, override: Override, *, at: datetime | None = None) -> Correction:
        """Keep an override.

        Args:
            override: The engineer's override. A correction read from another
                store is kept as a new row, with a new id and time.
            at: When it was made; now, if None.

        Returns:
            The correction as stored, with its id and time.

        Raises:
            StoreError: If the file is not a corrections store of this layout.
        """
        moment = (at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        fields = override.model_dump(mode="json", include=set(_COLUMNS))
        names = (*_COLUMNS, "created_at")
        with self._open(create=True) as connection:
            cursor = connection.execute(
                f"INSERT INTO corrections ({', '.join(names)}) "  # noqa: S608 - fixed column names
                f"VALUES ({', '.join('?' for _ in names)})",
                (*(fields[name] for name in _COLUMNS), moment),
            )
            row_id = cursor.lastrowid
        if row_id is None:
            msg = f"the corrections store {self.path} did not number the new row"
            raise StoreError(msg)
        return Correction(**fields, id=row_id, created_at=moment)

    def _select(self, query: str, parameters: Sequence[object]) -> list[Correction]:
        """Read corrections.

        Args:
            query: The whole SELECT statement.
            parameters: Its parameters.

        Returns:
            The rows as corrections, in the query's order; none from an
            absent store.
        """
        if not self.path.is_file():
            return []
        with self._open(create=False) as connection:
            if not _has_table(connection):
                return []
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [Correction.model_validate(dict(row)) for row in rows]

    def recall_for_part(self, category: str, *, limit: int = MAX_RECALL) -> list[Correction]:
        """Recall a part's most recent corrections.

        Args:
            category: The part.
            limit: The most corrections to give.

        Returns:
            The engineer's last word on each region of that part, most recent
            first, at most `limit`.

        Raises:
            ValueError: If `limit` is below one.
            StoreError: If the file is not a corrections store of this layout.
        """
        _check_limit(limit)
        return self._select(f"{_LATEST} ORDER BY kept.id DESC LIMIT ?", (category, limit))

    def recall_for_answer(
        self,
        category: str,
        defect_class: str | None,
        clause_id: str | None,
        *,
        limit: int = MAX_RECALL,
    ) -> list[Correction]:
        """Recall the corrections made where the judge gave this same answer before.

        Args:
            category: The part.
            defect_class: The class the judge names now; None if it names none.
            clause_id: The numbered heading it cites now; None with the class.
            limit: The most corrections to give.

        Returns:
            The engineer's last word on each region of that part that the
            judge had answered in the same way, most recent first, at most
            `limit`. A region the judge gave no valid answer for is never
            among them.

        Raises:
            ValueError: If `limit` is below one.
            StoreError: If the file is not a corrections store of this layout.
        """
        _check_limit(limit)
        return self._select(
            f"{_LATEST} AND kept.judged_class IS ? AND kept.judged_clause IS ? "
            "AND kept.judged_reason IS NOT NULL ORDER BY kept.id DESC LIMIT ?",
            (category, defect_class, clause_id, limit),
        )

    def for_image(self, category: str, image_id: str) -> list[Correction]:
        """List every override of one image, the history included.

        Args:
            category: The part.
            image_id: The image's name within its run.

        Returns:
            The image's overrides, most recent first.

        Raises:
            StoreError: If the file is not a corrections store of this layout.
        """
        return self._select(
            "SELECT * FROM corrections WHERE category = ? AND image_id = ? ORDER BY id DESC",
            (category, image_id),
        )

    def overridden(self, category: str, image_id: str) -> bool:
        """Say whether an engineer has overridden the judge on an image.

        Args:
            category: The part.
            image_id: The image's name within its run.

        Returns:
            True if the store holds an override of any region of the image.

        Raises:
            StoreError: If the file is not a corrections store of this layout.
        """
        return bool(self.for_image(category, image_id))

    def count(self) -> int:
        """Count the overrides held, the history included.

        Returns:
            The number of rows; zero for an absent store.

        Raises:
            StoreError: If the file is not a corrections store of this layout.
        """
        if not self.path.is_file():
            return 0
        with self._open(create=False) as connection:
            if not _has_table(connection):
                return 0
            return int(connection.execute("SELECT COUNT(*) FROM corrections").fetchone()[0])


def _has_table(connection: sqlite3.Connection) -> bool:
    """Say whether an open file holds the corrections table.

    Args:
        connection: The open file.

    Returns:
        False for an empty file, which a reader treats as an empty store.
    """
    found = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'corrections'"
    ).fetchone()[0]
    return bool(found)


def _check_limit(limit: int) -> None:
    """Refuse a recall of fewer than one correction.

    Args:
        limit: The most corrections asked for.

    Raises:
        ValueError: If it is below one.
    """
    if limit < 1:
        msg = f"recall gives at least 1 correction, got a limit of {limit}"
        raise ValueError(msg)
