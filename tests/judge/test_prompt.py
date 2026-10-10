"""Tests for the prompt builder: the contract of what the judge is shown, and in what order."""

import base64
import json
from collections.abc import Sequence
from typing import Any, cast

import pytest

from spec_to_inspector.judge.answer import AnswerError
from spec_to_inspector.judge.prompt import (
    FACTS_CLOSE,
    FACTS_OPEN,
    MAX_CORRECTIONS,
    NO_CORRECTIONS,
    build_messages,
    clause_prefix,
    measured_facts,
    repair_messages,
)
from spec_to_inspector.measure import MeasuredRegion, ZoneOverlap
from spec_to_inspector.spec.schema import Specification
from spec_to_inspector.spec.summary import clause_table_text
from tests.spec.spec_fakes import specification

CROP = b"\x89PNG crop"
OVERLAY = b"\x89PNG overlay"


def _region(**changes: object) -> MeasuredRegion:
    fields: dict[str, object] = {
        "label": 1,
        "area_px": 180,
        "area_mm2": 0.45000000000000007,
        "longest_extent_mm": 1.5000000000000002,
        "shortest_extent_mm": 0.30000000000000004,
        "centroid": (0.315, 0.50375),
        "bbox_px": (300, 400, 330, 406),
        "rectangle_px": ((300.0, 400.0), (330.0, 400.0), (330.0, 406.0), (300.0, 406.0)),
        "touches_border": False,
        "zone": "A",
        "zones": (
            ZoneOverlap(zone_id="A", rank=1, overlap_fraction=0.25, contains_centroid=False),
            ZoneOverlap(zone_id="B", rank=2, overlap_fraction=1.0, contains_centroid=True),
        ),
    }
    return MeasuredRegion.model_validate(fields | changes)


def _messages(
    *,
    spec: Specification | None = None,
    category: str = "pcb9",
    region: MeasuredRegion | None = None,
    from_peak: bool = False,
    corrections: Sequence[str] = (),
) -> list[dict[str, Any]]:
    built = build_messages(
        spec if spec is not None else specification(),
        category,
        region if region is not None else _region(),
        crop_png=CROP,
        overlay_png=OVERLAY,
        from_peak=from_peak,
        corrections=corrections,
    )
    return cast("list[dict[str, Any]]", built)


def _user_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(part["text"] for part in messages[1]["content"] if part["type"] == "text")


def _facts(messages: list[dict[str, Any]]) -> dict[str, Any]:
    text = _user_text(messages)
    return json.loads(text[text.index(FACTS_OPEN) + len(FACTS_OPEN) : text.index(FACTS_CLOSE)])


def test_the_clause_table_comes_first_and_whole() -> None:
    """The system message is the instructions and then the whole table, as U3 serialises it."""
    spec = specification()
    system, user = _messages(spec=spec)

    assert system["role"] == "system"
    assert system["content"] == clause_prefix(spec)
    assert system["content"].endswith(clause_table_text(spec))
    assert user["role"] == "user"


def test_the_prefix_does_not_depend_on_the_image_the_region_or_the_part() -> None:
    """Everything before the request is identical across images, so the server can cache it."""
    spec = specification()
    first = _messages(spec=spec)
    second = _messages(
        spec=spec,
        category="pcb1",
        region=_region(longest_extent_mm=9.0, zone="B"),
        corrections=["An engineer said so."],
    )

    assert first[0] == second[0]


def test_the_request_is_ordered_part_corrections_facts_crop_overlay() -> None:
    """What varies least comes first; the two pictures follow the facts, crop before overlay."""
    user = _messages()[1]

    kinds = [part["type"] for part in user["content"]]
    assert kinds == ["text", "image_url", "image_url", "text"]
    text = user["content"][0]["text"]
    order = [
        text.index("Part: pcb9"),
        text.index("4.1 Scratch"),
        text.index("Corrections"),
        text.index(FACTS_OPEN),
    ]
    assert order == sorted(order)
    crop, overlay = (part["image_url"]["url"] for part in user["content"][1:3])
    assert crop == "data:image/png;base64," + base64.b64encode(CROP).decode()
    assert overlay == "data:image/png;base64," + base64.b64encode(OVERLAY).decode()


def test_the_parts_headings_are_listed_with_their_classes() -> None:
    """The judge is told which headings are this part's, each once, with its class."""
    text = _user_text(_messages())

    assert '4.1 Scratch (defect_class "scratch")' in text
    assert '4.2 Missing component (defect_class "missing")' in text
    assert text.count("4.1 Scratch") == 1


def test_the_measured_facts_are_the_measurements_own_numbers_verbatim() -> None:
    """Every figure in the facts reads back as exactly the float the measurement holds."""
    region = _region()

    facts = _facts(_messages(region=region))

    assert facts == measured_facts(region, from_peak=False)
    assert facts["longest_extent_mm"] == region.longest_extent_mm == 1.5000000000000002
    assert facts["shortest_extent_mm"] == region.shortest_extent_mm
    assert facts["area_mm2"] == region.area_mm2
    assert facts["zone"] == "A"
    assert facts["zones_touched"] == [
        {"zone": "A", "share_of_region": 0.25},
        {"zone": "B", "share_of_region": 1.0},
    ]
    assert facts["touches_image_border"] is False
    assert facts["size_measured"] is True


def test_no_other_figure_than_the_measurements_enters_the_request() -> None:
    """Outside the facts and the headings' numbers, the request's text carries no digit."""
    text = _user_text(_messages())
    outside = text[: text.index(FACTS_OPEN)] + text[text.index(FACTS_CLOSE) :]
    for heading in ("4.1", "4.2", "pcb9"):
        outside = outside.replace(heading, "")

    assert not any(character.isdigit() for character in outside)


def test_a_region_outside_every_zone_says_so() -> None:
    """No zone is null in the facts, not a guess."""
    facts = _facts(_messages(region=_region(zone=None, zones=())))

    assert facts["zone"] is None
    assert facts["zones_touched"] == []


def test_a_peak_patch_gives_its_place_but_no_size() -> None:
    """A patch under the map's peak is a location; its extent is the patch's, so none is shown."""
    facts = _facts(_messages(from_peak=True))

    assert facts["size_measured"] is False
    assert "longest_extent_mm" not in facts
    assert "shortest_extent_mm" not in facts
    assert "area_mm2" not in facts
    assert facts["zone"] == "A"


def test_the_corrections_slot_is_always_present_and_empty_by_default() -> None:
    """With nothing recalled the slot says so, in the same place a correction would stand."""
    text = _user_text(_messages())

    assert NO_CORRECTIONS in text


def test_recalled_corrections_are_numbered_in_the_slot() -> None:
    """Up to three corrections stand before the facts, in the order given."""
    corrections = ["A dark smear on the receptacle is dirt, clause 4.1.", "Second.", "Third."]

    text = _user_text(_messages(corrections=corrections))

    assert NO_CORRECTIONS not in text
    for number, correction in enumerate(corrections, start=1):
        assert f"{number}. {correction}" in text
    assert text.index("1. A dark smear") < text.index("2. Second.") < text.index(FACTS_OPEN)


def test_more_corrections_than_the_slot_holds_are_refused() -> None:
    """The plan's three is a limit, enforced where the prompt is built."""
    with pytest.raises(ValueError, match=str(MAX_CORRECTIONS)):
        _messages(corrections=["one", "two", "three", "four"])


def test_an_empty_correction_is_refused() -> None:
    """A blank line in the slot would read as a correction that says nothing."""
    with pytest.raises(ValueError, match="empty"):
        _messages(corrections=["  "])


def test_a_repair_keeps_the_conversation_and_says_what_was_wrong() -> None:
    """The retry shows the model its own text and the fault, after the unchanged prompt."""
    messages = _messages()
    error = AnswerError("the board is scratched", "not JSON (Expecting value at character 0)")

    repaired = cast("list[dict[str, Any]]", repair_messages(messages, error))

    assert repaired[:2] == messages
    assert repaired[2] == {"role": "assistant", "content": "the board is scratched"}
    assert repaired[3]["role"] == "user"
    assert "not JSON" in repaired[3]["content"]
    assert "one JSON object" in repaired[3]["content"]
    assert len(messages) == 2
