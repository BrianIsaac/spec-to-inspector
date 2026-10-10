"""Tests for the rendering of a correction into the one line the judge is shown."""

from spec_to_inspector.corrections.render import render_correction
from spec_to_inspector.corrections.store import Override
from spec_to_inspector.judge.disposition import Outcome


def _override(**changes: object) -> Override:
    fields: dict[str, object] = {
        "category": "pcb4",
        "image_id": "bad-016",
        "region_index": 1,
        "crop_path": None,
        "judged_class": "burnt",
        "judged_clause": "5.7",
        "judged_outcome": Outcome.REJECT,
        "judged_reason": "A blackened area on the board surface",
        "corrected_class": "damage",
        "corrected_clause": "5.5",
        "note": "",
    }
    return Override.model_validate(fields | changes)


def test_a_correction_is_one_line_naming_both_classes_and_both_clauses() -> None:
    """What the judge called it, and what the engineer corrected it to."""
    assert render_correction(_override()) == (
        "On a pcb4 board the judge called the flagged area 'burnt' (clause 5.7); "
        "the engineer corrected it to 'damage' (clause 5.5)."
    )


def test_the_engineers_note_follows_in_their_own_words() -> None:
    """The note is quoted after the correction, with one full stop."""
    line = render_correction(_override(note="The capacitor is shattered, not burnt."))

    assert line == (
        "On a pcb4 board the judge called the flagged area 'burnt' (clause 5.7); "
        "the engineer corrected it to 'damage' (clause 5.5). "
        "The engineer's note: The capacitor is shattered, not burnt."
    )
    assert render_correction(_override(note="shattered capacitor")).endswith(
        "The engineer's note: shattered capacitor."
    )


def test_a_false_alarm_is_corrected_to_no_clause() -> None:
    """The engineer saying that nothing is wrong is rendered in words, not as null."""
    line = render_correction(_override(corrected_class=None, corrected_clause=None))

    assert line == (
        "On a pcb4 board the judge called the flagged area 'burnt' (clause 5.7); "
        "the engineer corrected it to no defect: no clause applies."
    )


def test_a_judge_that_found_no_clause_or_gave_no_answer_is_said_so() -> None:
    """The judged half has its own words when the judge named nothing."""
    nothing = render_correction(_override(judged_class=None, judged_clause=None))
    silent = render_correction(_override(judged_class=None, judged_clause=None, judged_reason=None))

    assert nothing.startswith(
        "On a pcb4 board the judge found no clause for the flagged area; the engineer"
    )
    assert silent.startswith(
        "On a pcb4 board the judge gave no valid answer for the flagged area; the engineer"
    )


def test_the_line_is_one_line_whatever_the_note() -> None:
    """A rendered correction never breaks the slot's numbering."""
    line = render_correction(_override(note="first\nsecond"))

    assert len(line.splitlines()) == 1
    assert "None" not in render_correction(_override(corrected_class=None, corrected_clause=None))
