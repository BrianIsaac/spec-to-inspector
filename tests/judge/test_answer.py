"""Tests for the judge's answer: its JSON schema and its validation."""

import json
import re
from typing import Any, cast

import pytest

from spec_to_inspector.judge.answer import (
    MAX_REASON_CHARACTERS,
    AnswerError,
    JudgeAnswer,
    answer_schema,
    parse_answer,
)
from tests.spec.spec_fakes import specification


def _properties(schema: dict[str, object]) -> dict[str, dict[str, Any]]:
    return cast("dict[str, dict[str, Any]]", schema["properties"])


def _answer(**changes: object) -> str:
    fields: dict[str, object] = {
        "reason": "a thin bright line scored across the board face",
        "defect_class": "scratch",
        "clause_id": "4.1",
    }
    return json.dumps(fields | changes)


def test_the_schema_offers_the_parts_own_headings_and_classes_and_a_way_out() -> None:
    """The answer is constrained to the part's headings and classes, or to neither."""
    schema = answer_schema(specification(), "pcb9")

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["reason", "defect_class", "clause_id"]
    properties = _properties(schema)
    assert list(properties) == ["reason", "defect_class", "clause_id"]
    assert properties["defect_class"] == {"enum": ["scratch", "missing", None]}
    assert properties["clause_id"] == {"enum": ["4.1", "4.2", None]}


def test_the_schema_bars_digits_and_line_breaks_from_the_reason() -> None:
    """Constrained decoding cannot put a figure into the model's sentence."""
    reason = _properties(answer_schema(specification(), "pcb9"))["reason"]

    assert reason["type"] == "string"
    pattern = re.compile(reason["pattern"])
    assert pattern.fullmatch("a dark charred patch beside the receptacle")
    assert not pattern.fullmatch("a scratch about 3 mm long")
    assert not pattern.fullmatch("two\nlines")
    assert not pattern.fullmatch("")
    assert pattern.fullmatch("x" * MAX_REASON_CHARACTERS)
    assert not pattern.fullmatch("x" * (MAX_REASON_CHARACTERS + 1))


def test_the_schema_of_a_part_the_specification_does_not_cover_offers_only_the_way_out() -> None:
    """A board the document says nothing about can only be referred."""
    properties = _properties(answer_schema(specification(), "pcb1"))

    assert properties["defect_class"] == {"enum": [None]}
    assert properties["clause_id"] == {"enum": [None]}


def test_a_valid_answer_is_read() -> None:
    """The three fields come back as the model wrote them."""
    answer = parse_answer(_answer())

    assert answer == JudgeAnswer(
        reason="a thin bright line scored across the board face",
        defect_class="scratch",
        clause_id="4.1",
    )


def test_an_answer_may_cite_nothing() -> None:
    """Null for both the class and the clause says no clause covers what is seen."""
    answer = parse_answer(_answer(defect_class=None, clause_id=None))

    assert answer.defect_class is None
    assert answer.clause_id is None
    assert not answer.cites_a_clause


def test_an_unknown_clause_is_still_an_answer() -> None:
    """Whether the clause exists is the rule's question, not the parser's."""
    assert parse_answer(_answer(clause_id="9.9")).clause_id == "9.9"


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("", "not JSON"),
        ("the board is scratched", "not JSON"),
        (f"```json\n{_answer()}\n```", "not JSON"),
        ('{"reason": "a", "defect_class": "scratch", "clause_id": "4.1"', "not JSON"),
        ("[1, 2]", "not a JSON object"),
        ('"scratch"', "not a JSON object"),
        (_answer(clause_id=None), "both or neither"),
        (_answer(defect_class=None), "both or neither"),
        (_answer(measured=3.2), "measured"),
        (_answer(clause_id=4.1), "clause_id"),
        (_answer(defect_class=7), "defect_class"),
        (_answer(defect_class="scratch of 3 mm"), "defect_class"),
        (_answer(defect_class="scratch; reject"), "defect_class"),
        (_answer(clause_id="clause 4.1"), "clause_id"),
        (_answer(clause_id="4.1 (limit 9 mm)"), "clause_id"),
        (_answer(reason=""), "reason"),
        (_answer(reason="x" * (MAX_REASON_CHARACTERS + 1)), "reason"),
        (_answer(reason="first line\nsecond line"), "one line"),
        (_answer(reason="first line\u2028second line"), "one line"),
        (_answer(reason="first line\x0csecond line"), "one line"),
        (_answer(reason="a scratch about 3 mm long"), "figure"),
        (_answer(reason="a scratch about \uff13 mm long"), "figure"),
        (_answer(reason="half the pad, \u00bd, is bare"), "figure"),
        ('{"reason": "a", "defect_class": "scratch"}', "clause_id"),
        ('{"reason": "a", "reason": "b", "defect_class": "scratch", "clause_id": "4.1"}', "twice"),
    ],
)
def test_a_malformed_answer_is_refused_with_the_cause(text: str, why: str) -> None:
    """Anything but the one JSON object the schema describes is an error in words."""
    with pytest.raises(AnswerError, match=why):
        parse_answer(text)


def test_white_space_around_the_object_and_inside_the_strings_is_dropped() -> None:
    """A server that pads its output still gives a clean answer."""
    answer = parse_answer(
        '\n {"reason": "  a lump of solder  ", "defect_class": " melt ", "clause_id": " 4.1 "}\n'
    )

    assert answer.reason == "a lump of solder"
    assert answer.defect_class == "melt"
    assert answer.clause_id == "4.1"


def test_the_error_carries_what_the_model_wrote() -> None:
    """The retry and the decision's record can quote the refused text."""
    with pytest.raises(AnswerError) as caught:
        parse_answer("the board is scratched")

    assert caught.value.text == "the board is scratched"
    assert "not JSON" in caught.value.problem


def test_a_class_is_words_and_a_clause_is_a_clause_number() -> None:
    """The two names are held to their shapes, so no free text rides in on them."""
    answer = parse_answer(_answer(defect_class="Wrong Place", clause_id="5.4"))

    assert answer.defect_class == "Wrong Place"
    assert answer.clause_id == "5.4"
    assert parse_answer(_answer(clause_id="5.6.1")).clause_id == "5.6.1"
