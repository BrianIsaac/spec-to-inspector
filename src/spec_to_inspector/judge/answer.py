"""The judge's answer: the JSON the model is held to, and its validation.

The model names what it sees in one line, a defect class and the numbered
heading of the clause that covers it, or says that no clause does. It is
given nothing else to fill: no size, no zone, no verdict. The schema is sent
to the server for constrained decoding and every answer is validated here
again, so a server that does not constrain is held to the same contract.

The reason is the model's own sentence and may not carry a figure: digits
and other numeric characters are barred, by the schema's pattern and by the
validation, so that no number a reader sees on a decision was written by the
model.

The pattern also bars the double quote and the backslash. It describes the
string's contents, so with a quote allowed the model can close the sentence
itself and go on to write the other fields inside the string, free of their
enums: a server that enforced the schema faithfully did exactly that.

The final figure holds that ban. The Stage II protocol's `designators` comparison lets one thing
through, a digit straight after a capital, as in `R12`, so that `5.67 mm` still cannot be written.
The pattern alone does not settle it: its class bars only 0 to 9, so `½` is the validation's to
refuse; its limit counts a designator as one, so the 240 characters are the validation's to hold;
and `R5 mm` passes both, which is why the bench lists every reason with a digit in it.
"""

import json
import re
from collections.abc import Mapping
from typing import Annotated, Final, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from spec_to_inspector.settings import ReasonRule
from spec_to_inspector.spec.schema import Specification

MAX_REASON_CHARACTERS: Final = 240
REASON_PATTERNS: Final[dict[ReasonRule, str]] = {
    "no_digits": f'^[^0-9\\n\\r"\\\\]{{1,{MAX_REASON_CHARACTERS}}}$',
    "designators": f'^(?:[^0-9\\n\\r"\\\\]|[A-Z][0-9]{{1,3}}){{1,{MAX_REASON_CHARACTERS}}}$',
}
"""The reason's pattern under each rule, as `eval/PROTOCOL-stage2.md` declares them."""
RECORDED: Final[Mapping[str, ReasonRule]] = {"reason_rule": "designators"}
"""The validation context for reading a decision back: it was held to its rule when it was made,
and the file does not say which that was, so the widest rule reads either."""
_DESIGNATOR: Final = re.compile(r"[A-Z][0-9]{1,3}(?![0-9])")

_ClassName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, strict=True, pattern=r"^[A-Za-z]+( [A-Za-z]+)*$"),
]
_ClauseNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, pattern=r"^[0-9]+(\.[0-9]+)*$")
]
_Reason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_REASON_CHARACTERS, strict=True
    ),
]


class AnswerError(ValueError):
    """The model's text is not the one JSON object the schema describes.

    Attributes:
        text: What the model wrote.
        problem: What is wrong with it, in words fit to send back to the model.
    """

    def __init__(self, text: str, problem: str) -> None:
        """Record the text and what is wrong with it.

        Args:
            text: What the model wrote.
            problem: What is wrong with it.
        """
        super().__init__(f"the answer is not valid: {problem}")
        self.text = text
        self.problem = problem


class JudgeAnswer(BaseModel):
    """What the model says of one region.

    Attributes:
        reason: One line on what is seen in the crop, in the model's words,
            without figures.
        defect_class: The defect class named, in words only, or None when no
            clause covers what is seen.
        clause_id: The numbered heading of the clause cited, a clause number
            and nothing else, or None with `defect_class`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: _Reason
    defect_class: _ClassName | None
    clause_id: _ClauseNumber | None

    @field_validator("reason")
    @classmethod
    def _one_line_without_figures(cls, value: str, info: ValidationInfo) -> str:
        """Refuse a reason that runs over a line or states a figure.

        Args:
            value: The reason, stripped.
            info: The validation's context, which may name the rule; `no_digits` if it does not.

        Returns:
            The reason unchanged.

        Raises:
            ValueError: If it holds a line break or a numeric character.
        """
        if len(value.splitlines()) > 1:
            msg = "the reason must be one line"
            raise ValueError(msg)
        context = cast("Mapping[str, ReasonRule] | None", info.context)
        rule = context["reason_rule"] if context else "no_digits"
        words = _DESIGNATOR.sub("", value) if rule == "designators" else value
        if any(character.isnumeric() for character in words):
            msg = "the reason must not state a figure: sizes are measured, not judged"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        """Refuse a class without a clause and a clause without a class.

        Returns:
            The answer unchanged.

        Raises:
            ValueError: If exactly one of the two is null.
        """
        if (self.defect_class is None) != (self.clause_id is None):
            msg = "defect_class and clause_id must both be given or both be null: both or neither"
            raise ValueError(msg)
        return self

    @property
    def cites_a_clause(self) -> bool:
        """Whether the model named a class and a clause, as against neither."""
        return self.clause_id is not None


def answer_schema(
    specification: Specification, category: str, *, reason_rule: ReasonRule = "no_digits"
) -> dict[str, object]:
    """Give the JSON schema of an answer about one part.

    The class and the clause are held to the part's own classes and numbered
    headings; null for both is the way out when none of them covers what is
    seen. The reason comes first, so the model describes before it names.

    Args:
        specification: The parsed specification.
        category: The part the board is.
        reason_rule: What the reason may hold.

    Returns:
        A JSON schema for constrained decoding; a part the specification does
        not cover gets a schema that allows only the null answer.
    """
    clauses = [clause for clause in specification.clauses if clause.category == category]
    classes = list(dict.fromkeys(clause.defect_class for clause in clauses))
    headings = list(dict.fromkeys(clause.heading_id for clause in clauses))
    return {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "pattern": REASON_PATTERNS[reason_rule],
            },
            "defect_class": {"enum": [*classes, None]},
            "clause_id": {"enum": [*headings, None]},
        },
        "required": ["reason", "defect_class", "clause_id"],
        "additionalProperties": False,
    }


def _no_repeats(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object, refusing a key given twice.

    Args:
        pairs: The object's keys and values, in the order written.

    Returns:
        The object.

    Raises:
        ValueError: If a key appears more than once.
    """
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        msg = f"{', '.join(repeated)} given twice"
        raise ValueError(msg)
    return dict(pairs)


def parse_answer(text: str, *, reason_rule: ReasonRule = "no_digits") -> JudgeAnswer:
    """Read the model's text as an answer.

    Whether the clause exists and whether the class is the clause's are not
    checked here: those are the disposition rule's questions, and an answer
    that fails them is referred to an engineer, not sent back to the model.

    Args:
        text: What the model wrote.
        reason_rule: What the reason may hold.

    Returns:
        The answer.

    Raises:
        AnswerError: If the text is not exactly one JSON object with the
            three fields, each of its type.
    """
    try:
        value: object = json.loads(text, object_pairs_hook=_no_repeats)
    except json.JSONDecodeError as error:
        raise AnswerError(text, f"not JSON ({error.msg} at character {error.pos})") from error
    except ValueError as error:
        raise AnswerError(text, str(error)) from error
    if not isinstance(value, dict):
        raise AnswerError(text, "not a JSON object")
    try:
        return JudgeAnswer.model_validate(value, context={"reason_rule": reason_rule})
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in issue['loc']) or 'answer'}: {issue['msg']}"
            for issue in error.errors()
        )
        raise AnswerError(text, problems) from error
