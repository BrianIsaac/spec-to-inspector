"""The prompt builder: what the judge is shown about one region, and in what order.

The order is the contract, and it is chosen for the server's prefix cache.
What never changes between images comes first, what changes least comes next:

1. the system message: the instructions, then the whole clause table as
   `spec.summary.clause_table_text` gives it. It depends on the specification
   alone, so a server that caches prompt prefixes evaluates it once;
2. the request: the part and its numbered headings; the corrections slot
   (engineers' corrections recalled for this board, at most three, or a line
   saying there are none); the measured facts, which are the measurement's
   own numbers as JSON; then the crop and the same crop under the anomaly
   heatmap; then the question.

The model is asked for a class, a heading and a line of description. Every
figure it is shown is a measurement or the clause table's, and it is told to
write none.
"""

import base64
import json
from collections.abc import Sequence
from typing import Final

from spec_to_inspector.judge.answer import AnswerError
from spec_to_inspector.judge.client import Message
from spec_to_inspector.measure import MeasuredRegion
from spec_to_inspector.spec.schema import Specification
from spec_to_inspector.spec.summary import clause_table_text

MAX_CORRECTIONS: Final = 3
NO_CORRECTIONS: Final = "None recorded for this board."
FACTS_OPEN: Final = "<measured>"
FACTS_CLOSE: Final = "</measured>"

_INSTRUCTIONS: Final = """\
You are the visual judge on a printed circuit board inspection line. An anomaly detector has \
flagged one area of a board. You are shown that area twice: first the crop as photographed, then \
the same crop with the detector's heatmap drawn on the flagged area, outlined in white and \
coloured from blue at its edge to red at its peak. Say which defect the flagged area shows and \
which clause of the customer's workmanship specification covers it.

Answer with one JSON object and nothing else, with these three fields in this order:
- "reason": one line describing what you see in the flagged area. Describe only. Do not state \
sizes, counts or any other figures: sizes are measured by the inspector, not by you.
- "defect_class": the defect class of the clause you cite, spelled exactly as in the clause table.
- "clause_id": the "heading_id" of that clause. Cite only a clause of the part named in the \
request.

If the flagged area shows nothing that a clause of that part covers, answer null for both \
"defect_class" and "clause_id". You do not decide whether the board is accepted or rejected and \
you do not apply any limit: the inspector applies the clause's limit to its own measurement.

The specification is "{title}". Its clause table follows, one JSON object per clause.
"""

_QUESTION: Final = (
    "Which defect does the flagged area show, and which clause covers it? "
    "Answer with the JSON object only."
)

_REPAIR: Final = (
    "That answer was not valid: {problem}. Answer again with exactly one JSON object holding "
    '"reason", "defect_class" and "clause_id", and nothing else. The reason is one line without '
    "figures."
)


def clause_prefix(specification: Specification) -> str:
    """Give the part of the prompt that is the same for every image: the system message.

    Args:
        specification: The parsed specification.

    Returns:
        The instructions followed by the whole clause table as compact JSON.
    """
    return _INSTRUCTIONS.format(title=specification.title) + clause_table_text(specification)


def measured_facts(region: MeasuredRegion, *, from_peak: bool) -> dict[str, object]:
    """Give what was measured of a region, as the prompt states it.

    Every number is the measurement's own value, unrounded. A region that is
    only the patch under the anomaly map's peak has a place but no size of its
    own, so its extents are left out.

    Args:
        region: The measured region.
        from_peak: Whether the region is the anomaly model's peak-patch fallback.

    Returns:
        The facts, ready to be written as JSON.
    """
    facts: dict[str, object] = {
        "zone": region.zone,
        "zones_touched": [
            {"zone": overlap.zone_id, "share_of_region": overlap.overlap_fraction}
            for overlap in region.zones
        ],
        "touches_image_border": region.touches_border,
        "size_measured": not from_peak,
    }
    if not from_peak:
        facts |= {
            "longest_extent_mm": region.longest_extent_mm,
            "shortest_extent_mm": region.shortest_extent_mm,
            "area_mm2": region.area_mm2,
        }
    return facts


def _headings(specification: Specification, category: str) -> str:
    """List a part's numbered headings, each once, with its title and class.

    Args:
        specification: The parsed specification.
        category: The part.

    Returns:
        The headings on one line, or a sentence saying the part has none.
    """
    seen: dict[str, str] = {}
    for clause in specification.clauses:
        if clause.category == category:
            seen.setdefault(
                clause.heading_id,
                f'{clause.heading_id} {clause.title} (defect_class "{clause.defect_class}")',
            )
    if not seen:
        return "The specification has no clause for this part."
    return "The clauses of this part, by heading_id: " + "; ".join(seen.values()) + "."


def _corrections(corrections: Sequence[str]) -> str:
    """Lay out the corrections slot.

    Args:
        corrections: The recalled corrections, each already in words.

    Returns:
        The numbered corrections, or the line saying there are none.

    Raises:
        ValueError: If there are more than the slot holds, or one is empty.
    """
    if len(corrections) > MAX_CORRECTIONS:
        msg = f"the prompt holds at most {MAX_CORRECTIONS} corrections, got {len(corrections)}"
        raise ValueError(msg)
    lines = [" ".join(correction.split()) for correction in corrections]
    if not all(lines):
        msg = "a correction is empty"
        raise ValueError(msg)
    if not lines:
        return NO_CORRECTIONS
    return "\n".join(f"{number}. {line}" for number, line in enumerate(lines, start=1))


def _image(png: bytes) -> dict[str, object]:
    """Wrap a PNG as an image part of a chat message.

    Args:
        png: The PNG file's bytes.

    Returns:
        The part, with the image inline as a data URL.
    """
    encoded = base64.b64encode(png).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}


def build_messages(
    specification: Specification,
    category: str,
    region: MeasuredRegion,
    *,
    crop_png: bytes,
    overlay_png: bytes,
    from_peak: bool = False,
    corrections: Sequence[str] = (),
) -> list[Message]:
    """Build the conversation that asks the judge about one region.

    Args:
        specification: The parsed specification.
        category: The part the board is.
        region: The region as measured.
        crop_png: The crop of the source image around the region, as PNG.
        overlay_png: The same crop under the anomaly heatmap, as PNG.
        from_peak: Whether the region is the anomaly model's peak-patch
            fallback, whose size is not a defect's.
        corrections: Engineers' corrections recalled for this board, each one
            rendered in words by the corrections store; at most
            `MAX_CORRECTIONS`. Empty until that store exists.

    Returns:
        The system message and the request, in the OpenAI shape.

    Raises:
        ValueError: If there are too many corrections, or one is empty.
    """
    facts = json.dumps(measured_facts(region, from_peak=from_peak), separators=(",", ":"))
    request = "\n".join(
        [
            f"Part: {category}",
            _headings(specification, category),
            "",
            "Corrections recorded by engineers on earlier boards of this part; follow them "
            "where they apply:",
            _corrections(corrections),
            "",
            "What the inspector measured of the flagged area. These are facts, not yours to "
            "change or repeat:",
            f"{FACTS_OPEN}{facts}{FACTS_CLOSE}",
            "",
            "The first image is the crop. The second image is the same crop with the heatmap.",
        ]
    )
    return [
        {"role": "system", "content": clause_prefix(specification)},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": request},
                _image(crop_png),
                _image(overlay_png),
                {"type": "text", "text": _QUESTION},
            ],
        },
    ]


def repair_messages(messages: Sequence[Message], error: AnswerError) -> list[Message]:
    """Extend a conversation with a refused answer and the request to answer again.

    The original messages stay as they were, so the server's cache still
    holds them; the model sees its own text and what was wrong with it.

    Args:
        messages: The conversation that produced the refused answer.
        error: The refusal, with the model's text and the fault in words.

    Returns:
        A new conversation: the original, the refused answer, the repair request.
    """
    return [
        *messages,
        {"role": "assistant", "content": error.text},
        {"role": "user", "content": _REPAIR.format(problem=error.problem)},
    ]
