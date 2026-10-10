"""Tests for the corrections sink the override form writes to."""

import pytest
from pydantic import ValidationError

from spec_to_inspector.app.sink import CorrectionSink, InMemorySink, Override
from spec_to_inspector.judge.disposition import Outcome


def _override(**changes: object) -> Override:
    fields: dict[str, object] = {
        "category": "pcb4",
        "run": "test",
        "image_id": "bad-016",
        "region_index": 1,
        "crop_path": "/runs/pcb4/test/bad-016/crops/region-001.png",
        "judged_outcome": Outcome.REJECT,
        "judged_class": "burnt",
        "judged_clause": "5.7",
        "judged_reason": "A blackened area on the board surface.",
        "corrected_class": "damage",
        "corrected_clause": "5.5",
        "note": "The capacitor is shattered, not charred.",
        "created_at": "2026-10-11T02:00:00+00:00",
    }
    return Override.model_validate(fields | changes)


def test_the_in_memory_sink_is_a_correction_sink() -> None:
    """The default satisfies the protocol the console is written to."""
    assert isinstance(InMemorySink(), CorrectionSink)


def test_an_override_recorded_is_listed_for_its_image_only() -> None:
    """Overrides are kept per part, run and image."""
    sink = InMemorySink()
    sink.record(_override())

    assert sink.overrides_for("pcb4", "test", "bad-016") == (_override(),)
    assert sink.overrides_for("pcb4", "test", "bad-017") == ()
    assert sink.overrides_for("pcb4", "line-3", "bad-016") == ()
    assert sink.overrides_for("pcb1", "test", "bad-016") == ()


def test_overrides_of_one_image_come_back_newest_first() -> None:
    """A second correction of the same image does not replace the first; it is listed above it."""
    sink = InMemorySink()
    first = _override()
    second = _override(corrected_class="dirt", corrected_clause="5.1", note="On a second look.")
    sink.record(first)
    sink.record(second)

    assert sink.overrides_for("pcb4", "test", "bad-016") == (second, first)


def test_a_correction_to_no_defect_names_neither_class_nor_clause() -> None:
    """The engineer may say the flagged area is not a defect at all."""
    override = _override(corrected_class=None, corrected_clause=None)

    assert override.says_no_defect


@pytest.mark.parametrize(
    "changes",
    [
        {"corrected_class": "damage", "corrected_clause": None},
        {"corrected_class": None, "corrected_clause": "5.5"},
        {"note": "   "},
        {"note": "x" * 301},
        {"region_index": 0},
        {"image_id": ""},
    ],
)
def test_an_incomplete_override_is_refused(changes: dict[str, object]) -> None:
    """A class without its clause, a blank note and a region that does not exist are refused."""
    with pytest.raises(ValidationError):
        _override(**changes)


def test_the_note_is_kept_as_one_line() -> None:
    """A note typed over several lines is folded, as the corrections store keeps it."""
    assert _override(note="  Cracked body,\n  not charred.\n").note == "Cracked body, not charred."
