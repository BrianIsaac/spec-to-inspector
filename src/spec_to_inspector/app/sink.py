"""Where the console sends an engineer's override, and reads back the ones on an image.

The reject card's form writes to this protocol and to nothing else. `serve`
joins it to the corrections store the judge recalls from
(`spec_to_inspector.app.store_sink`); the default here keeps overrides in the
console's memory, so a console can be built with no store at all.
"""

from collections.abc import Sequence
from threading import Lock
from typing import Annotated, Final, Protocol, Self, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from spec_to_inspector.judge.disposition import Outcome

MAX_NOTE_CHARACTERS: Final = 300
"""The longest note kept; the corrections store's own limit, so every note the form takes fits."""

_Name = Annotated[str, StringConstraints(min_length=1)]
_Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_NOTE_CHARACTERS)]


class OverrideRefusedError(ValueError):
    """The sink will not keep an override as given; the message is fit to show on the card."""


class SinkError(RuntimeError):
    """The sink cannot keep or list overrides at all; the message says why."""


class Override(BaseModel):
    """One correction by an engineer of what the judge said about a flagged area.

    Attributes:
        category: The part the board is.
        run: The batch's name within the part, the run directory's own name.
        image_id: The image's name within the run.
        region_index: The index of the flagged area corrected, from 1, as the
            anomaly model ranked it.
        crop_path: The crop the judge was shown, as a path; None if there was none.
        judged_outcome: The area's outcome as judged, before the correction.
        judged_class: The defect class the model named; None if it named none.
        judged_clause: The clause heading the model cited; None if it cited none.
        judged_reason: The model's own line of description; None if no valid
            answer came.
        corrected_class: The defect class the engineer gives; None when the
            engineer says the area is not a defect.
        corrected_clause: The clause heading the engineer gives; None with
            `corrected_class`.
        note: Why, in the engineer's words: one line of at most
            `MAX_NOTE_CHARACTERS`. The form asks for one; a correction made
            by the `correct` verb may have none.
        created_at: When the override was recorded, in UTC, ISO 8601.
    """

    model_config = ConfigDict(frozen=True)

    category: _Name
    run: _Name
    image_id: _Name
    region_index: int = Field(ge=1)
    crop_path: str | None = None
    judged_outcome: Outcome
    judged_class: str | None = None
    judged_clause: str | None = None
    judged_reason: str | None = None
    corrected_class: _Name | None = None
    corrected_clause: _Name | None = None
    note: _Note = ""
    created_at: _Name

    @field_validator("note", mode="before")
    @classmethod
    def _one_line(cls, value: object) -> object:
        """Fold a note typed over several lines into one, as the store keeps it."""
        return " ".join(value.split()) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _class_and_clause_together(self) -> Self:
        if (self.corrected_class is None) != (self.corrected_clause is None):
            msg = "a correction names a defect class and its clause together, or neither"
            raise ValueError(msg)
        return self

    @property
    def says_no_defect(self) -> bool:
        """Whether the engineer says the flagged area is not a defect."""
        return self.corrected_class is None


@runtime_checkable
class CorrectionSink(Protocol):
    """What the console needs of a corrections store."""

    @property
    def reaches_judge(self) -> bool:
        """Whether an override kept here is shown to the judge on later boards."""
        ...

    def record(self, override: Override) -> None:
        """Keep an override.

        Args:
            override: The engineer's correction.

        Raises:
            OverrideRefusedError: If the sink will not keep this override.
            SinkError: If the sink cannot keep overrides at all.
        """
        ...

    def overrides_for(self, category: str, run: str, image_id: str) -> Sequence[Override]:
        """List the overrides recorded on one image, the newest first.

        Args:
            category: The part.
            run: The batch's name within the part.
            image_id: The image's name within the run.

        Returns:
            The image's overrides; empty if it has none.

        Raises:
            SinkError: If the sink cannot be read.
        """
        ...


class InMemorySink:
    """A sink that keeps overrides for the life of the console's process."""

    def __init__(self) -> None:
        """Start with no override recorded."""
        self._overrides: list[Override] = []
        self._lock = Lock()

    @property
    def reaches_judge(self) -> bool:
        """False: the judge recalls from the corrections store, never from here."""
        return False

    def record(self, override: Override) -> None:
        """Keep an override.

        Args:
            override: The engineer's correction.
        """
        with self._lock:
            self._overrides.append(override)

    def overrides_for(self, category: str, run: str, image_id: str) -> tuple[Override, ...]:
        """List the overrides recorded on one image, the newest first.

        Args:
            category: The part.
            run: The batch's name within the part.
            image_id: The image's name within the run.

        Returns:
            The image's overrides; empty if it has none.
        """
        with self._lock:
            kept = [
                override
                for override in self._overrides
                if (override.category, override.run, override.image_id) == (category, run, image_id)
            ]
        return tuple(reversed(kept))
