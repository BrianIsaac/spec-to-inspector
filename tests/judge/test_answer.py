"""Tests for the judge's answer: its JSON schema and its validation."""

import itertools
import json
import re
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from pydantic import ValidationError

from spec_to_inspector.judge.answer import (
    MAX_REASON_CHARACTERS,
    REASON_PATTERNS,
    RECORDED,
    AnswerError,
    JudgeAnswer,
    RefusalKind,
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


def test_the_reason_cannot_swallow_the_rest_of_the_answer() -> None:
    """A quote in the reason would let the model write the other fields inside the string.

    The text is what Qwen3-VL-8B wrote about pcb1's bad-085 under vLLM's constrained decoding, on
    6 November 2026: a class and a clause the part does not have, then a note, all of it within
    the reason's pattern, until the length limit forced the closing quote. Only white space was
    then left to it, up to the token limit.
    """
    pattern = re.compile(_properties(answer_schema(specification(), "pcb9"))["reason"]["pattern"])

    swallowed = (
        'A foreign object, likely a fiber, lying on the board surface.", '
        '"defect_class": "dirt", "clause_id": "none"}  // Note: No clause covers it'
    )
    assert not pattern.fullmatch(swallowed)
    assert not pattern.fullmatch(r"a mark with a back\\slash")
    assert pattern.fullmatch("a mark, irregular: dark (charred) - on the board's edge.")


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


EVAL = Path(__file__).parents[2] / "eval"
PROTOCOL = EVAL / "PROTOCOL-stage2.md"
PATTERN_ADDITION = EVAL / "PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md"
COUNTED = r'^(?:[^0-9\n\r"\\]|[A-Z][0-9]{1,3}){1,240}$'
"""The pattern the protocol first declared, whose strings the addition's must be exactly."""
SIZES_THE_MODEL_WROTE = (
    "A stray solder lump on the board surface, 5.67 mm long.",
    "A stray fiber on the board surface, 1.57 mm long.",
    "Foreign material on the receptacle, 1.5 mm in size.",
)
"""What Qwen3-VL-8B wrote when told to put a size in digits with no schema, on week 1's boards."""


def _designators() -> re.Pattern[str]:
    schema = answer_schema(specification(), "pcb9", reason_rule="designators")
    return re.compile(_properties(schema)["reason"]["pattern"])


def test_the_final_pattern_is_the_one_the_protocol_declares() -> None:
    """The protocol's table is the final setting's word, and the addition does not touch it."""
    assert f"`{REASON_PATTERNS['no_digits']}`" in PROTOCOL.read_text(encoding="utf-8")


def test_the_designators_pattern_is_the_one_the_addition_rules() -> None:
    """The addition's text, its character count gone: `+` in place of `{1,240}`."""
    ruling = PATTERN_ADDITION.read_text(encoding="utf-8")

    assert f"`{REASON_PATTERNS['designators']}`" in ruling
    assert REASON_PATTERNS["designators"].endswith(")+$")
    assert "240" not in REASON_PATTERNS["designators"]
    assert f"`{COUNTED}`" in ruling


def test_the_uncounted_pattern_accepts_exactly_the_protocols_strings() -> None:
    """Every string of up to six characters over an alphabet that reaches each branch."""
    counted, uncounted = re.compile(COUNTED), _designators()
    alphabet = 'aR1.\n"\\½'
    strings = (
        "".join(characters)
        for length in range(7)
        for characters in itertools.product(alphabet, repeat=length)
    )

    differing = [s for s in strings if bool(counted.fullmatch(s)) != bool(uncounted.fullmatch(s))]
    assert differing == []


@pytest.mark.parametrize("unit", ["a", "R12", "R123"])
def test_the_two_patterns_part_only_past_the_count_the_validation_holds_anyway(unit: str) -> None:
    """At 240 repeats both accept; past them only the uncounted, and the validation refuses it."""
    counted, uncounted = re.compile(COUNTED), _designators()

    assert counted.fullmatch(unit * 240)
    assert uncounted.fullmatch(unit * 240)
    assert not counted.fullmatch(unit * 241)
    assert uncounted.fullmatch(unit * 241)
    with pytest.raises(AnswerError, match="reason") as refused:
        parse_answer(_answer(reason=unit * 241), reason_rule="designators")
    assert refused.value.kind is RefusalKind.OVER_LENGTH


def test_the_final_setting_keeps_the_ban_unless_the_comparison_is_asked_for() -> None:
    """The default schema and validation are the ones the final figure is declared with."""
    reason = _properties(answer_schema(specification(), "pcb9"))["reason"]

    assert reason["pattern"] == REASON_PATTERNS["no_digits"]
    assert not re.fullmatch(reason["pattern"], "a resistor R12 with a mark on it")
    with pytest.raises(AnswerError, match="must not state a figure"):
        parse_answer(_answer(reason="a resistor R12 with a mark on it"))


@pytest.mark.parametrize(
    "reason",
    [
        "A resistor R12 is present and correctly placed but has foreign material on it.",
        "Solder bridges U3 and C12 on the header",
        "R1, R22 and R333 all carry the same mark",
        "No designator at all, only words.",
    ],
)
def test_a_designator_passes_the_pattern_and_the_validation(reason: str) -> None:
    """A digit straight after a capital is what the comparison lets through."""
    assert _designators().fullmatch(reason)
    assert parse_answer(_answer(reason=reason), reason_rule="designators").reason == reason


@pytest.mark.parametrize(
    "reason",
    [
        *SIZES_THE_MODEL_WROTE,
        "12.5 mm",
        "5mm",
        "a scratch 3 mm long",
        "A 5 mm scratch",
        "R12.5 across",
        "R1234 is a part number",
        "r12 in lower case",
        "two\nlines from R12",
        'R12", "defect_class": "dirt',
    ],
)
def test_a_size_in_digits_does_not_pass_the_pattern(reason: str) -> None:
    """Every digit needs a capital straight before it, and at most three follow it."""
    assert not _designators().fullmatch(reason)


@pytest.mark.parametrize("reason", [*SIZES_THE_MODEL_WROTE, "12.5 mm", "R1234 is a part number"])
def test_a_size_in_digits_does_not_pass_the_validation(reason: str) -> None:
    """A server that does not constrain is held to the same contract."""
    with pytest.raises(AnswerError, match="must not state a figure"):
        parse_answer(_answer(reason=reason), reason_rule="designators")


@pytest.mark.parametrize(
    "reason", ["about ½ of the pad", "R٣ beside the pad", "R12 and \uff15 more"]
)
def test_a_figure_the_pattern_cannot_see_is_refused_by_the_validation(reason: str) -> None:
    """`½` is week 1's fifth retry: the pattern's class only bars 0 to 9, the validation all."""
    assert _designators().fullmatch(reason)
    with pytest.raises(AnswerError, match="must not state a figure"):
        parse_answer(_answer(reason=reason), reason_rule="designators")


def test_the_validation_holds_the_reason_to_its_length_whatever_the_pattern_allows() -> None:
    """The pattern has no limit, so 240 characters are the validation's alone to hold."""
    long = "R12 " * 100

    assert len(long) > MAX_REASON_CHARACTERS
    assert _designators().fullmatch(long)
    with pytest.raises(AnswerError, match="reason"):
        parse_answer(_answer(reason=long), reason_rule="designators")


def test_a_capital_then_a_digit_then_a_unit_passes_which_is_why_reasons_are_listed() -> None:
    """The protocol says so: `R5 mm` can be written, so the pattern alone does not show it."""
    assert _designators().fullmatch("R5 mm")
    assert parse_answer(_answer(reason="R5 mm"), reason_rule="designators").reason == "R5 mm"


def test_a_recorded_answer_is_read_back_under_the_widest_rule() -> None:
    """A decision the comparison wrote can still be read; a figure outside one still cannot."""
    answer = {"reason": "a mark on R12", "defect_class": "scratch", "clause_id": "4.1"}

    assert JudgeAnswer.model_validate(answer, context=RECORDED).reason == "a mark on R12"
    with pytest.raises(ValidationError):
        JudgeAnswer.model_validate(answer)
    with pytest.raises(ValidationError):
        JudgeAnswer.model_validate(answer | {"reason": "5 mm"}, context=RECORDED)


@pytest.mark.parametrize(
    ("text", "rule", "kind"),
    [
        ('{"reason": "a stray mark on the pad a a a a', "designators", RefusalKind.NOT_JSON),
        ("not an object at all", "no_digits", RefusalKind.NOT_JSON),
        ("[1, 2]", "no_digits", RefusalKind.OTHER),
        (_answer(reason="a scratch 5 mm long"), "designators", RefusalKind.FIGURE),
        (_answer(reason="a mark on R12"), "no_digits", RefusalKind.FIGURE),
        (_answer(reason="two\nlines"), "no_digits", RefusalKind.OTHER),
        (_answer(reason="a" * 241), "designators", RefusalKind.OVER_LENGTH),
        (_answer(reason="a" * 241), "no_digits", RefusalKind.OVER_LENGTH),
        (_answer(clause_id=None), "no_digits", RefusalKind.OTHER),
    ],
)
def test_a_refused_answer_says_what_kind_of_refusal_it_is(
    text: str, rule: Literal["no_digits", "designators"], kind: RefusalKind
) -> None:
    """The record counts each kind under its own heading, so the kind is the validation's word."""
    with pytest.raises(AnswerError) as refused:
        parse_answer(text, reason_rule=rule)

    assert refused.value.kind is kind
