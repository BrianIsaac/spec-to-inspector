"""A correction in words: the one line the judge is shown in the prompt's slot."""

from spec_to_inspector.corrections.store import Override


def _judged(override: Override) -> str:
    """Say what the judge made of the region.

    Args:
        override: The override.

    Returns:
        The clause of the sentence about the judge.
    """
    if override.judged_class is not None:
        return (
            f"the judge called the flagged area '{override.judged_class}' "
            f"(clause {override.judged_clause})"
        )
    if override.judged_reason is not None:
        return "the judge found no clause for the flagged area"
    return "the judge gave no valid answer for the flagged area"


def render_correction(override: Override) -> str:
    """Render a correction as one line of words for the judge's prompt.

    The line names the class and the clause on both sides and quotes the
    engineer's note, which is where the engineer says what to look for. The
    clause numbers are the specification's and the note is the engineer's:
    nothing in the line was written by the model.

    Args:
        override: The override, stored or not.

    Returns:
        One line, such as "On a pcb4 board the judge called the flagged area
        'burnt' (clause 5.7); the engineer corrected it to 'damage' (clause
        5.5). The engineer's note: the capacitor is shattered."
    """
    corrected = (
        f"'{override.corrected_class}' (clause {override.corrected_clause})"
        if override.corrected_class is not None
        else "no defect: no clause applies"
    )
    line = (
        f"On a {override.category} board {_judged(override)}; "
        f"the engineer corrected it to {corrected}."
    )
    note = override.note.rstrip(".").rstrip()
    return f"{line} The engineer's note: {note}." if note else line
