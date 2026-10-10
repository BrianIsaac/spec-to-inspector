"""What the reject card draws and takes: a board's flagged areas, and the engineer's correction.

The card shows fields, not prose of its own: the clause is the decision's
clause, the figures are the measurement's and the rule's, the sentence under
the verdict is the one code wrote, and the model's sentence is shown apart
and labelled as the model's. This module adds only geometry (the measured
rectangle moved into the crop's pixels) and the checking of the override form
against the specification in force.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from spec_to_inspector.anomaly.records import Region
from spec_to_inspector.app.runs import BoardDetail, RunError
from spec_to_inspector.app.sink import MAX_NOTE_CHARACTERS
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.decision import Decision, RegionDecision
from spec_to_inspector.spec.schema import Specification


def prompt_corrections(judged: RegionDecision | None) -> tuple[str, ...]:
    """Give the engineers' corrections that stood in the prompt for one area.

    Args:
        judged: The area's record in the decision.

    Returns:
        Each correction as the judge read it; empty where the area was not
        judged or was judged with none in view.
    """
    return () if judged is None else judged.corrections


def first_answer(judged: RegionDecision | None) -> JudgeAnswer | None:
    """Give the model's answer before it was shown corrections, where it was asked twice.

    Args:
        judged: The area's record in the decision.

    Returns:
        The first answer, or None where the area was asked once or not at all.
    """
    return None if judged is None else judged.first_answer


_INDEX_DIGITS: Final = 6


class FormError(ValueError):
    """The override form does not hold together; the message is fit to show beside it."""


@dataclass(frozen=True)
class RegionCard:
    """One flagged area of a board, as the card draws it.

    Attributes:
        index: The area's index, from 1, as the anomaly model ranked it.
        found: The area as the anomaly model located it.
        judged: What the judge and the rule made of it; None if it was not judged.
        deciding: Whether the board's outcome rests on this area.
        width: The crop's width in source pixels; 0 without a crop.
        height: The crop's height in source pixels; 0 without a crop.
        extent: The measured minimum-area rectangle as SVG polygon points in
            the crop's own pixels; None where no size was measured.
    """

    index: int
    found: Region
    judged: RegionDecision | None
    deciding: bool
    width: int
    height: int
    extent: str | None

    @property
    def has_crop(self) -> bool:
        """Whether the run holds a crop of this area."""
        return self.found.crop is not None and self.found.crop_box is not None

    @property
    def has_overlay(self) -> bool:
        """Whether the judge left the overlay it was shown."""
        return self.judged is not None and self.judged.overlay is not None


def _extent(found: Region, judged: RegionDecision | None) -> str | None:
    """Move the measured rectangle from the source image into the crop.

    Args:
        found: The area as the anomaly model located it, with its crop's rectangle.
        judged: The judge's record of the area, with the measurement.

    Returns:
        The rectangle's corners as SVG polygon points; None where there is no
        crop, no measurement, or the area is a peak patch, whose size is the
        patch's and not a defect's.
    """
    box = found.crop_box
    if box is None or judged is None or judged.measurement is None or judged.from_peak:
        return None
    return " ".join(f"{x - box.x:.1f},{y - box.y:.1f}" for x, y in judged.measurement.rectangle_px)


def region_cards(detail: BoardDetail) -> list[RegionCard]:
    """Lay out every flagged area of a board, judged or not, in rank order.

    Args:
        detail: The board with its result and its decision.

    Returns:
        One card per area the anomaly model located.
    """
    decision = detail.decision
    judged = {region.index: region for region in decision.regions} if decision else {}
    deciding = decision.deciding_region if decision else None
    cards: list[RegionCard] = []
    for found in detail.result.regions:
        box = found.crop_box
        cards.append(
            RegionCard(
                index=found.index,
                found=found,
                judged=judged.get(found.index),
                deciding=found.index == deciding,
                width=box.width if box else 0,
                height=box.height if box else 0,
                extent=_extent(found, judged.get(found.index)),
            )
        )
    return cards


def choose_region(cards: Sequence[RegionCard], asked: int | None) -> RegionCard | None:
    """Pick the area a card opens on.

    Args:
        cards: The board's areas.
        asked: The area asked for, or None for the card's own choice.

    Returns:
        The area asked for; else the one the outcome rests on; else the first
        judged; else the first; None for a board with no flagged area.

    Raises:
        RunError: If the board has no area of the index asked for.
    """
    if asked is not None:
        chosen = next((card for card in cards if card.index == asked), None)
        if chosen is None:
            msg = f"the board has no flagged area {asked}"
            raise RunError(msg)
        return chosen
    deciding = next((card for card in cards if card.deciding), None)
    if deciding is not None:
        return deciding
    judged = next((card for card in cards if card.judged is not None), None)
    if judged is not None:
        return judged
    return cards[0] if cards else None


@dataclass(frozen=True)
class ClauseChoice:
    """One clause heading the engineer may correct to.

    Attributes:
        heading_id: The numbered heading, which is what the judge cites.
        title: The heading's title.
        defect_class: The defect class the heading covers.
    """

    heading_id: str
    title: str
    defect_class: str


def clause_choices(specification: Specification, category: str) -> list[ClauseChoice]:
    """List a part's clause headings, in the document's order.

    Args:
        specification: The specification in force.
        category: The part.

    Returns:
        One choice per numbered heading of the part; empty if the
        specification has no clause for it.
    """
    choices: dict[str, ClauseChoice] = {}
    for clause in specification.clauses:
        if clause.category == category:
            choices.setdefault(
                clause.heading_id,
                ClauseChoice(clause.heading_id, clause.title, clause.defect_class),
            )
    return list(choices.values())


def check_correction(
    specification: Specification, category: str, *, defect_class: str, clause: str
) -> tuple[str | None, str | None]:
    """Check the class and the clause an engineer corrects to against the specification.

    Args:
        specification: The specification in force.
        category: The board's part.
        defect_class: The class chosen; empty for "not a defect".
        clause: The clause heading chosen; empty for "not a defect".

    Returns:
        The class and the heading, or None and None for "not a defect".

    Raises:
        FormError: If only one of the two is given, either is not the part's,
            or the heading covers another class.
    """
    defect_class, clause = defect_class.strip(), clause.strip()
    if not defect_class and not clause:
        return None, None
    if not defect_class or not clause:
        msg = (
            "a correction names the defect class and its clause together, "
            "or neither for an area that is not a defect"
        )
        raise FormError(msg)
    choices = {choice.heading_id: choice for choice in clause_choices(specification, category)}
    if defect_class not in {choice.defect_class for choice in choices.values()}:
        msg = f"the specification has no defect class {defect_class!r} for part {category}"
        raise FormError(msg)
    if clause not in choices:
        msg = f"the specification has no clause {clause} for part {category}"
        raise FormError(msg)
    if choices[clause].defect_class != defect_class:
        msg = f"clause {clause} is for class {choices[clause].defect_class!r}, not {defect_class!r}"
        raise FormError(msg)
    return defect_class, clause


def check_note(note: str) -> str:
    """Check the engineer's note and fold it to one line.

    Args:
        note: The note as typed.

    Returns:
        The note on one line.

    Raises:
        FormError: If it is blank or too long to keep.
    """
    folded = " ".join(note.split())
    if not folded:
        raise FormError("say why: a correction is kept with the engineer's note")
    if len(folded) > MAX_NOTE_CHARACTERS:
        msg = (
            f"the note is {len(folded)} characters; a correction's note is at most "
            f"{MAX_NOTE_CHARACTERS} characters"
        )
        raise FormError(msg)
    return folded


def region_number(text: str) -> int | None:
    """Read a flagged area's index as a form sent it.

    Args:
        text: The form's value.

    Returns:
        The index, or None if the text is not a number an index could be.
    """
    digits = text.strip()
    # A board has a handful of areas; a longer run of digits is not an index, and Python
    # refuses to convert thousands of them.
    return int(digits) if digits.isdecimal() and len(digits) <= _INDEX_DIGITS else None


def judged_region(decision: Decision, image_id: str, region: str) -> RegionDecision:
    """Find the judged area a correction is about.

    Args:
        decision: The board's decision.
        image_id: The board's name, for the message.
        region: The area's index as the form sent it.

    Returns:
        The area's record in the decision.

    Raises:
        FormError: If the text is not the index of an area the judge answered for.
    """
    index = region_number(region)
    found = next((r for r in decision.regions if r.index == index), None)
    if found is None:
        said = region.strip()[:12] or "(none given)"
        msg = f"board {image_id} has no judged area {said}"
        raise FormError(msg)
    return found


def form_defaults(
    specification: Specification, category: str, answer: JudgeAnswer | None
) -> tuple[str, str]:
    """Give the clause and the class the override form opens on: the judge's own, made consistent.

    The form starts from what the judge said, so the engineer changes only
    what is wrong. The judge may cite a row of a heading, or a class that is
    not its clause's; the form's two fields must belong together, so the
    clause leads and its class follows.

    Args:
        specification: The specification in force.
        category: The board's part.
        answer: The model's answer for the area; None if no valid answer came.

    Returns:
        The clause heading and its defect class; two empty strings ("not a
        defect") where the judge named nothing the part's clauses hold.
    """
    if answer is None:
        return "", ""
    choices = {choice.heading_id: choice for choice in clause_choices(specification, category)}
    cited = answer.clause_id
    if cited is not None and cited not in choices:
        row = specification.find(cited)
        cited = row.heading_id if row is not None and row.category == category else None
    if cited is not None and cited in choices:
        return cited, choices[cited].defect_class
    for choice in choices.values():
        if choice.defect_class == answer.defect_class:
            return choice.heading_id, choice.defect_class
    return "", ""
