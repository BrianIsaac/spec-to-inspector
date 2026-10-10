"""The corrections store as the console's sink: the join to the corrections loop.

An override recorded on a card ends in the same call as the `correct` verb's,
`corrections.override.record_override`: the judged half is read from the
board's `decision.json`, the engineer's clause is checked against the part's
table, the row goes into the store the judge recalls from, and the decision
is flagged as overridden. The card's list is the store's history of the image.
"""

from collections.abc import Callable
from pathlib import Path

from spec_to_inspector.app.runs import RunError, open_run
from spec_to_inspector.app.sink import Override, OverrideRefusedError, SinkError
from spec_to_inspector.corrections.override import OverrideError, record_override
from spec_to_inspector.corrections.store import Correction, CorrectionStore, StoreError
from spec_to_inspector.spec.schema import Specification


class StoreSink:
    """A sink over the corrections store.

    The store's key is the part and the image's name; it has no batch. The
    console's batch is used to find the board on disk, and two batches of one
    part that hold an image of the same name share its corrections.
    """

    def __init__(
        self,
        store: CorrectionStore,
        *,
        runs_dir: Path,
        specification: Callable[[], Specification | None],
    ) -> None:
        """Bind the sink to a store and to where the boards are.

        Args:
            store: The corrections store.
            runs_dir: The runs directory the console serves.
            specification: Gives the specification in force when an override
                is recorded, or None if there is none.
        """
        self._store = store
        self._runs_dir = runs_dir
        self._specification = specification

    @property
    def reaches_judge(self) -> bool:
        """True: `inspect` recalls a part's corrections from this store into the judge's prompt."""
        return True

    def record(self, override: Override) -> None:
        """Store an override and flag the board's decision as overridden.

        The override says which area of which board and what the engineer
        corrects it to; what the judge had said is read again from the
        decision on disk, so the row holds the judgement as it stands.

        Args:
            override: The engineer's correction.

        Raises:
            OverrideRefusedError: If there is no specification in force, the board
                is not in the runs directory, or the corrections loop will
                not make the override as asked. Nothing is stored then,
                unless the message says the row is kept and only the flag
                could not be written.
            SinkError: If the store's file cannot be used.
        """
        specification = self._specification()
        if specification is None:
            msg = "no specification is in force, so the correction's clause cannot be checked"
            raise OverrideRefusedError(msg)
        try:
            board = open_run(self._runs_dir, override.category, override.run).board(
                override.image_id
            )
        except RunError as error:
            raise OverrideRefusedError(str(error)) from error
        try:
            record_override(
                self._store,
                board.directory,
                specification,
                region_index=override.region_index,
                clause_id=override.corrected_clause,
                defect_class=override.corrected_class,
                note=override.note,
            )
        except OverrideError as error:
            raise OverrideRefusedError(str(error)) from error
        except StoreError as error:
            raise SinkError(str(error)) from error

    def overrides_for(self, category: str, run: str, image_id: str) -> tuple[Override, ...]:
        """List the store's overrides of one image, the newest first.

        Args:
            category: The part.
            run: The batch's name within the part.
            image_id: The image's name within the run.

        Returns:
            The image's overrides, the history included; empty if it has none.

        Raises:
            SinkError: If the store's file cannot be read.
        """
        try:
            rows = self._store.for_image(category, image_id)
        except StoreError as error:
            raise SinkError(str(error)) from error
        return tuple(_as_override(row, run) for row in rows)


def _as_override(row: Correction, run: str) -> Override:
    """Give a stored correction in the console's own shape.

    Args:
        row: The correction as the store holds it.
        run: The batch the card is open on; the store keeps none.

    Returns:
        The override.
    """
    return Override(
        category=row.category,
        run=run,
        image_id=row.image_id,
        region_index=row.region_index,
        crop_path=row.crop_path,
        judged_outcome=row.judged_outcome,
        judged_class=row.judged_class,
        judged_clause=row.judged_clause,
        judged_reason=row.judged_reason,
        corrected_class=row.corrected_class,
        corrected_clause=row.corrected_clause,
        note=row.note,
        created_at=row.created_at,
    )
