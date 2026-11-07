"""What `inspect` leaves for people: a reject card per rejected board, and the batch's report.

Everything here is read back from the run's directory, so the files say what the decisions on disk
say, whichever boards this judging touched: a re-judged board can lose its card. The pages are
static and show fields, not prose of their own, in the console's own style. The console draws the
same decision live, with the override form, which a file cannot hold.

    <run>/
        report.html                     the counts, and one row per board
        report.css                      the console's stylesheet
        clauses.json                    the clause table the run judged against, where it parsed one
        <image_id>/reject-card.html     a rejected board's card
"""

import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Final

from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.judge.decision import Decision, RegionDecision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import (
    DECISION_NAME,
    RESULT_NAME,
    load_decision,
    read_run_index,
)
from spec_to_inspector.spec.schema import Clause

REPORT_NAME: Final = "report.html"
STYLE_NAME: Final = "report.css"
CARD_NAME: Final = "reject-card.html"
CLAUSE_TABLE_NAME: Final = "clauses.json"
_ALLOCATION_UNIT: Final = 512
_STATUS: Final[dict[Outcome, tuple[str, str]]] = {
    Outcome.ACCEPT: ("accept", "Accept"),
    Outcome.REJECT: ("reject", "Reject"),
    Outcome.NEEDS_REVIEW: ("needs-review", "Needs review"),
}


class ReportWritten(BaseModel):
    """What a batch left: the boards by outcome, the cards, and the sizes on disk.

    Attributes:
        boards: Boards of the run.
        accepted: Boards accepted.
        rejected: Boards rejected.
        referred: Boards referred to an engineer.
        not_judged: Boards with no decision on disk.
        cards: Reject cards written.
        report_bytes: The report and its stylesheet, in bytes.
        report_disk_bytes: The same, as allocated on the disk.
        cards_bytes: The reject cards, in bytes.
        cards_disk_bytes: The same, as allocated on the disk.
        run_bytes: Every file of the run's directory, in bytes.
        run_disk_bytes: The same, as allocated on the disk.
    """

    model_config = ConfigDict(frozen=True)

    boards: int
    accepted: int
    rejected: int
    referred: int
    not_judged: int
    cards: int
    report_bytes: int
    report_disk_bytes: int
    cards_bytes: int
    cards_disk_bytes: int
    run_bytes: int
    run_disk_bytes: int


@dataclass(frozen=True)
class _Row:
    """One board's row in the report."""

    image_id: str
    status: str
    outcome: str
    clause: Clause | None
    reason: str
    card: str | None


def _environment() -> Environment:
    """Make the pages' template environment, escaping everything from the records.

    Returns:
        The environment.
    """
    return Environment(
        loader=PackageLoader("spec_to_inspector.batch", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _sizes(paths: list[Path]) -> tuple[int, int]:
    """Read some files' sizes from the disk.

    Args:
        paths: The files.

    Returns:
        Their size in bytes, and what is allocated for them.
    """
    stats = [path.stat() for path in paths]
    return (
        sum(stat.st_size for stat in stats),
        sum(stat.st_blocks * _ALLOCATION_UNIT for stat in stats),
    )


def _card_region(decision: Decision) -> RegionDecision | None:
    """Name the region a rejected board's card shows.

    Args:
        decision: The board's decision.

    Returns:
        The region the outcome rests on, or the first if it rests on none, or None if none exists.
    """
    resting = next((r for r in decision.regions if r.index == decision.deciding_region), None)
    return resting or (decision.regions[0] if decision.regions else None)


def _crop_shape(directory: Path, region: RegionDecision | None) -> tuple[int, int]:
    """Read the size of the crop a card shows, so that its frame keeps the crop's shape.

    Args:
        directory: The board's directory.
        region: The region the card shows.

    Returns:
        The crop's width and height; a square where the record names none.
    """
    if region is None:
        return (1, 1)
    result = ImageResult.model_validate_json((directory / RESULT_NAME).read_text(encoding="utf-8"))
    found = next((r for r in result.regions if r.index == region.index), None)
    box = None if found is None else found.crop_box
    return (1, 1) if box is None else (box.width, box.height)


def write_report(run_directory: Path) -> ReportWritten:
    """Write the reject cards and the report of a run, from its decisions on disk.

    Args:
        run_directory: The run's directory, holding `run.json` and each board's decision.

    Returns:
        What was written, and how much of the disk it and the run take.

    Raises:
        InspectError: If the directory is not a run.
    """
    index = read_run_index(run_directory)
    environment = _environment()
    card_template = environment.get_template("reject-card.html")
    rows: list[_Row] = []
    cards: list[Path] = []
    counts = dict.fromkeys(Outcome, 0)
    not_judged = 0
    specification = ""
    for entry in index.entries:
        directory = run_directory / entry.image_id
        card = directory / CARD_NAME
        if not (directory / DECISION_NAME).is_file():
            card.unlink(missing_ok=True)
            not_judged += 1
            rows.append(_Row(entry.image_id, "not-judged", "Not yet judged", None, "", None))
            continue
        decision = load_decision(directory)
        specification = specification or decision.specification
        counts[decision.outcome] += 1
        status, words = _STATUS[decision.outcome]
        rejected = decision.outcome is Outcome.REJECT
        if rejected:
            region = _card_region(decision)
            width, height = _crop_shape(directory, region)
            card.write_text(
                card_template.render(
                    decision=decision,
                    region=region,
                    crop_width=width,
                    crop_height=height,
                    run_name=run_directory.name,
                    report=REPORT_NAME,
                    style=STYLE_NAME,
                ),
                encoding="utf-8",
            )
            cards.append(card)
        else:
            card.unlink(missing_ok=True)
        rows.append(
            _Row(
                image_id=entry.image_id,
                status=status,
                outcome=words,
                clause=decision.clause,
                reason=decision.reason,
                card=f"{entry.image_id}/{CARD_NAME}" if rejected else None,
            )
        )

    style = run_directory / STYLE_NAME
    source = files("spec_to_inspector.app") / "static" / "console.css"
    with source.open("rb") as reading, style.open("wb") as writing:
        shutil.copyfileobj(reading, writing)
    report = run_directory / REPORT_NAME
    tallied = ReportWritten(
        boards=len(index.entries),
        accepted=counts[Outcome.ACCEPT],
        rejected=counts[Outcome.REJECT],
        referred=counts[Outcome.NEEDS_REVIEW],
        not_judged=not_judged,
        cards=len(cards),
        report_bytes=0,
        report_disk_bytes=0,
        cards_bytes=0,
        cards_disk_bytes=0,
        run_bytes=0,
        run_disk_bytes=0,
    )
    report.write_text(
        environment.get_template("report.html").render(
            run_name=run_directory.name,
            category=index.category,
            specification=specification,
            written=tallied,
            rows=rows,
            style=STYLE_NAME,
        ),
        encoding="utf-8",
    )
    report_bytes, report_disk_bytes = _sizes([report, style])
    cards_bytes, cards_disk_bytes = _sizes(cards)
    run_bytes, run_disk_bytes = _sizes([p for p in run_directory.rglob("*") if p.is_file()])
    return tallied.model_copy(
        update={
            "report_bytes": report_bytes,
            "report_disk_bytes": report_disk_bytes,
            "cards_bytes": cards_bytes,
            "cards_disk_bytes": cards_disk_bytes,
            "run_bytes": run_bytes,
            "run_disk_bytes": run_disk_bytes,
        }
    )
