"""The whole batch's page and its `two-runs.md`, made from the files alone.

Nothing here is typed by hand: every figure comes from a record `inspect --record` wrote, from what
the wrapper on the machine wrote, or from the raw digests read before the first run. So one command
gives both files again:

    .venv/bin/python -m spec_to_inspector.batch.page results/stage2/batch
"""

import argparse
import csv
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, cast

from spec_to_inspector.batch.record import BatchRecord, read_batch_record
from spec_to_inspector.bench.checkpoints import read_checkpoint_record
from spec_to_inspector.bench.record import StageTimes
from spec_to_inspector.bench.run import stage_times
from spec_to_inspector.judge.timing import Spread

PARTS: Final = ("pcb1", "pcb4")
RUNS: Final = ("run-1", "run-2")
PAGE_NAME: Final = "README.md"
TWO_RUNS_NAME: Final = "two-runs.md"
DIGESTS_NAME: Final = "digests-week2.txt"
_BYTES_PER_MIB: Final = 1024**2
_SECTIONS: Final[dict[str, str]] = {
    "times": "Figure 7: `times`",
    "report_seconds": "Figure 7: `report_seconds`, `whole_seconds`",
    "whole_seconds": "Figure 7: `report_seconds`, `whole_seconds`",
    "inspector": "Figure 8: `inspector`",
    "memory": "Figure 9: `memory`",
    "judge_memory": "Figure 9: `judge_memory`",
    "run": "The anomaly model's stage: `run`",
    "counts": "The boards: `counts`",
    "report": "The cards and the report: `report`",
    "judge": "How the judge was asked: `judge`",
    "specification": "The specification: `specification`, `clause_table`",
    "clause_table": "The specification: `specification`, `clause_table`",
    "leak": "The void rules: `leak`, `on_threshold`, `refused_answers`",
    "on_threshold": "The void rules: `leak`, `on_threshold`, `refused_answers`",
    "refused_answers": "The void rules: `leak`, `on_threshold`, `refused_answers`",
    "observations": "Board by board: `observations`",
}
_OTHER_SECTION: Final = "What the record is made of"
_BOARD_FIELDS: Final = ("flagged", "score", "outcome", "cited_heading", "cited_class", "sentence")
_FINAL_FIELDS: Final = (
    "score",
    "flagged",
    "regions_found",
    "citation",
    "cited_heading",
    "cited_class",
    "sentence",
    "row_id",
    "outcome",
    "review_cause",
)
"""What a board's line holds that is not a time, to set each run against the final's second."""


@dataclass(frozen=True)
class Wrapped:
    """What the wrapper on the machine wrote of one step.

    Attributes:
        start: When it started, UTC.
        end: When it ended, UTC.
        exit: Its exit code.
        pid: Its process.
    """

    start: str
    end: str
    exit: str
    pid: str


@dataclass(frozen=True)
class OneRun:
    """One run of the batch, as its files hold it.

    Attributes:
        name: `run-1` or `run-2`.
        records: Each part's record.
        wrapper: What the wrapper wrote of the whole run.
        parts: What the wrapper wrote of each part.
        whole_readings: Every reading of both cards the wrapper took.
    """

    name: str
    records: dict[str, BatchRecord]
    wrapper: Wrapped
    parts: dict[str, Wrapped]
    whole_readings: list[dict[str, str]]


def _read_step(raw: Path, name: str) -> Wrapped:
    """Read what the wrapper wrote of one step.

    Args:
        raw: The directory of the raw files.
        name: The step's name.

    Returns:
        The step.
    """

    def field(suffix: str) -> str:
        return (raw / f"{name}.{suffix}").read_text(encoding="utf-8").strip()

    return Wrapped(start=field("start"), end=field("end"), exit=field("exit"), pid=field("pid"))


def read_run(directory: Path, name: str, record_stem: str) -> OneRun:
    """Read one run's files.

    Args:
        directory: The batch's directory.
        name: `run-1` or `run-2`.
        record_stem: What the records' names begin with, up to the part.

    Returns:
        The run.
    """
    raw = directory / "raw"
    with (raw / f"{name}.cards.csv").open(encoding="utf-8", newline="") as handle:
        readings = list(csv.DictReader(handle))
    return OneRun(
        name=name,
        records={
            part: read_batch_record(directory / f"{record_stem}{part}.json") for part in PARTS
        },
        wrapper=_read_step(raw, name),
        parts={part: _read_step(raw, f"{name}.{part}") for part in PARTS},
        whole_readings=readings,
    )


def wall_clock_seconds(step: Wrapped) -> int:
    """Count a step's wall clock from the wrapper's two stamps.

    Args:
        step: The step.

    Returns:
        Whole seconds, the stamps' resolution.
    """
    return int(
        (datetime.fromisoformat(step.end) - datetime.fromisoformat(step.start)).total_seconds()
    )


def _clock(seconds: float) -> str:
    """Write a duration as minutes and seconds.

    Args:
        seconds: The duration.

    Returns:
        `9 min 56 s`.
    """
    whole = round(seconds)
    return f"{whole // 60} min {whole % 60} s"


def _pooled(run: OneRun) -> StageTimes:
    """Count figure 7 over both parts, by the bench's function.

    The parse is the first part's: a specification is parsed once, and each part's own is listed.

    Args:
        run: The run.

    Returns:
        The times.
    """
    records = [run.records[part] for part in PARTS]
    return stage_times(
        records[0].specification.parse_seconds,
        {record.part: record.run for record in records},
        [line for record in records for line in record.observations],
        sum(record.times.judge_stage_seconds for record in records),
    )


def _p50_p95(spread: Spread | None) -> str:
    """Write a median and a 95th percentile.

    Args:
        spread: The spread, if there was one.

    Returns:
        The two, in seconds.
    """
    return "None" if spread is None else f"{spread.p50:.2f} s, {spread.p95:.2f} s"


def _table(head: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    """Lay a Markdown table out.

    Args:
        head: The columns' names.
        rows: The rows.

    Returns:
        Its lines.
    """
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return lines


def _digest_lines(directory: Path) -> list[str]:
    """Lay the digests read before the first run beside the ones the protocol names.

    Args:
        directory: The batch's directory; the named ones are in `checkpoints.json` beside it.

    Returns:
        The section's lines.
    """
    raw = (directory / "raw" / DIGESTS_NAME).read_text(encoding="utf-8")
    second = dict(
        re.findall(r"^([0-9a-f]{64})\s+\S*/week2/run-2/\S*/(pcb\d)/model\.ckpt$", raw, re.M)
    )
    second = {part: digest for digest, part in second.items()}
    differing = dict(
        re.findall(r"^\$ cmp -l \S*patchcore/(pcb\d)/\S* \S* \| wc -l\n(\d+)$", raw, re.M)
    )
    named = read_checkpoint_record(directory.parent / "checkpoints.json").named
    rows = [
        (
            part,
            f"`{named[part].sha256}`",
            f"`{second[part]}`",
            f"{named[part].bytes:,}",
            differing[part],
        )
        for part in PARTS
    ]
    return [
        "## The digests, read before the first run",
        "",
        f"`sha256sum ~/week2/run-2/models/patchcore/*/model.ckpt` read against "
        f"`results/stage2/checkpoints.json`; the raw reading is `raw/{DIGESTS_NAME}`.",
        "",
        *_table(
            (
                "Part",
                "The named checkpoint",
                "Week 2's second training",
                "Bytes",
                "Bytes differing",
            ),
            rows,
        ),
        "",
    ]


def _whole_peaks(run: OneRun) -> tuple[int | None, int | None]:
    """Read the peaks of both cards over the whole run, from the wrapper's own readings.

    Args:
        run: The run.

    Returns:
        Card 0's and card 1's.
    """

    def peak(column: str) -> int | None:
        values = [round(float(row[column])) for row in run.whole_readings if row[column]]
        return max(values, default=None)

    return peak("card_0_mib"), peak("card_1_mib")


def _head_lines() -> list[str]:
    """Write the page's opening.

    Returns:
        Its lines.
    """
    return [
        "# Stage II: the whole batch, end to end",
        "",
        "One command per part, `spec-to-inspector inspect`, from the specification's PDF to the "
        "reject cards, over every board of the test split of pcb1 and pcb4, on the machine, in the "
        "final's setting. Two runs, the second after nothing was changed. This page is made from "
        "the files beside it by `python -m spec_to_inspector.batch.page`.",
        "",
        "**It gives no accuracy figure.** The final figure stands, in `results/stage2/final/`, and "
        "is not re-read from a batch. Run 2's records are `pcb1.json` and `pcb4.json`; run 1's are "
        "kept as `first-run.pcb1.json` and `first-run.pcb4.json`; every value that differs between "
        f"them is in `{TWO_RUNS_NAME}`.",
        "",
    ]


def _runs_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay out when each run and each part ran, as the wrapper wrote it.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    rows: list[Sequence[object]] = []
    for run in runs:
        steps = [(run.name, run.wrapper)]
        steps += [(f"{run.name}, {part}", run.parts[part]) for part in PARTS]
        rows.extend(
            (name, step.start, step.end, _clock(wall_clock_seconds(step)), step.pid, step.exit)
            for name, step in steps
        )
    return [
        "## The runs",
        "",
        "Times UTC, as the wrapper wrote them; the raw files are under `raw/`. Pids are the "
        "wrapper's for a run and the process's for a part. A run's wall clock includes the 5 s the "
        "wrapper waits after the last part, so that a last reading of the cards falls after it.",
        "",
        *_table(("Step", "Start", "End", "Wall clock", "Pid", "Exit"), rows),
        "",
    ]


def _boards_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay out what became of the boards.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    rows: list[Sequence[object]] = []
    for run in runs:
        records = [run.records[part] for part in PARTS]
        for record in records:
            counts = record.counts
            causes = ", ".join(f"{cause} {n}" for cause, n in counts.referred_by_cause.items())
            rows.append(
                (
                    run.name,
                    record.part,
                    counts.boards,
                    counts.accepted,
                    counts.rejected,
                    counts.referred,
                    causes or "None",
                    record.report.cards,
                )
            )
        rows.append(
            (
                run.name,
                "both",
                sum(r.counts.boards for r in records),
                sum(r.counts.accepted for r in records),
                sum(r.counts.rejected for r in records),
                sum(r.counts.referred for r in records),
                "",
                sum(r.report.cards for r in records),
            )
        )
    head = ("Run", "Part", "Boards", "Accepted", "Rejected", "Referred", "By cause", "Cards")
    return ["## What became of the boards", "", *_table(head, rows), ""]


def _against_final_lines(directory: Path, runs: Sequence[OneRun]) -> list[str]:
    """Set each run's boards against the final's second run, line by line.

    This asks whether `inspect` and the bench are one pipeline in the one setting. It counts boards
    whose fields differ, and no citation against any label.

    Args:
        directory: The batch's directory; the final's record is in `final/` beside it.
        runs: The runs.

    Returns:
        The section's lines; none if the final's record is not there.
    """
    path = directory.parent / "final" / "bench.json"
    if not path.is_file():
        return []
    final = cast("dict[str, list[dict[str, object]]]", json.loads(path.read_text(encoding="utf-8")))
    lines = {(str(line["part"]), str(line["image_id"])): line for line in final["observations"]}
    rows: list[Sequence[object]] = []
    for run in runs:
        boards = [line for part in PARTS for line in run.records[part].observations]
        differing = [
            sum(
                cast("object", getattr(board, field))
                != lines[(board.part, board.image_id)].get(field)
                for board in boards
            )
            for field in _FINAL_FIELDS
        ]
        rows.append((run.name, len(boards), *differing))
    return [
        "## Against the final's second run, board by board",
        "",
        "Each run's line for each board against `results/stage2/final/bench.json`, by every field "
        "that is not a time: how many boards differ. This asks whether `inspect` and the bench are "
        "one pipeline in the one setting. It re-reads no figure.",
        "",
        *_table(("Run", "Boards", *_FINAL_FIELDS), rows),
        "",
    ]


def _sizes_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay out the sizes of the cards, the report and the run on disk.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    rows = [
        (
            run.name,
            part,
            f"{r.report_bytes / _BYTES_PER_MIB:.2f}, {r.report_disk_bytes / _BYTES_PER_MIB:.2f}",
            f"{r.cards_bytes / _BYTES_PER_MIB:.2f}, {r.cards_disk_bytes / _BYTES_PER_MIB:.2f}",
            f"{r.run_bytes / _BYTES_PER_MIB:.1f}, {r.run_disk_bytes / _BYTES_PER_MIB:.1f}",
        )
        for run in runs
        for part in PARTS
        for r in (run.records[part].report,)
    ]
    return [
        "## The reject cards and the report, on disk",
        "",
        "Each size is in MiB, as the files' bytes and then as allocated on the disk. The report is "
        "`report.html` and its stylesheet; the run's directory is everything the part's run left "
        "on the machine. Run 2's reports are kept under `raw/reports/`; their links to the cards "
        "work on the machine, where the cards are.",
        "",
        *_table(("Run", "Part", "The report", "The cards", "The run's directory"), rows),
        "",
    ]


def _figure_seven_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay figure 7 out over both parts.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    pooled = [_pooled(run) for run in runs]

    def spreads(what: str, of: str) -> list[object]:
        return [what, *(_p50_p95(cast("Spread | None", getattr(times, of))) for times in pooled)]

    rows: list[Sequence[object]] = [
        [
            f"Parsing the specification, {part}'s run",
            *(f"{run.records[part].times.parse_seconds:.2f} s" for run in runs),
        ]
        for part in PARTS
    ]
    rows += [
        [
            f"The anomaly model, per image, {part}, with its file writing",
            *(f"{times.anomaly_seconds_per_image[part]:.4f} s" for times in pooled),
        ]
        for part in PARTS
    ]
    rows += [
        spreads("Measuring and drawing, per flagged image", "measure_and_draw_seconds"),
        spreads("The VLM, per question", "vlm_seconds_per_area"),
        spreads("The VLM, per flagged image", "vlm_seconds_per_flagged_image"),
        spreads("A flagged image, end to end", "flagged_image_seconds"),
        ["Flagged images", *(times.flagged_images for times in pooled)],
        ["Questions asked", *(times.areas_asked for times in pooled)],
        ["The judge's stage, both parts", *(_clock(t.judge_stage_seconds) for t in pooled)],
        [
            "Writing the cards and the report, both parts",
            *(f"{sum(run.records[p].report_seconds for p in PARTS):.2f} s" for run in runs),
        ],
    ]
    return [
        "## Figure 7: time per image, by stage",
        "",
        "After the warm-up, by the bench's own function over both parts. Each time with a "
        "distribution is its median, then its 95th percentile.",
        "",
        *_table(("Stage", *(run.name for run in runs)), rows),
        "",
    ]


def _figure_eight_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay figure 8 out, per part and for both.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    rows: list[Sequence[object]] = []
    for run in runs:
        records = [run.records[part] for part in PARTS]
        rows.extend(
            (
                run.name,
                record.part,
                f"{record.inspector.parse_seconds:.2f} s",
                f"{record.inspector.fit_seconds[record.part]:.1f} s",
                f"{record.inspector.minutes_all_parts:.2f}",
            )
            for record in records
        )
        fits = sum(record.inspector.fit_seconds[record.part] for record in records)
        parsed = records[0].inspector.parse_seconds
        rows.append(
            (run.name, "both", f"{parsed:.2f} s", f"{fits:.1f} s", f"{(parsed + fits) / 60:.2f}")
        )
    return [
        "## Figure 8: minutes from specification to a working inspector",
        "",
        "The parse time measured in this run plus the fit time recorded when each part's model was "
        "trained on the machine, week 2's first training. Training is not repeated here. Both "
        "parts is the pcb1 run's parse and both fits, since a specification is parsed once.",
        "",
        *_table(("Run", "Part", "Parse", "Fit", "Minutes"), rows),
        "",
    ]


def _figure_nine_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay figure 9 out, by stage and over the whole of each run.

    Args:
        runs: The runs.

    Returns:
        The section's lines.
    """
    memory = runs[-1].records[PARTS[0]].memory
    rows: list[Sequence[object]] = []
    for run in runs:
        for part in PARTS:
            rows.extend(
                (run.name, part, stage, peaks.anomaly_card_mib, peaks.judge_card_mib, peaks.samples)
                for stage, peaks in run.records[part].memory.by_stage.items()
            )
        zero, one = _whole_peaks(run)
        rows.append(
            (run.name, "the whole run, the wrapper's", "", zero, one, len(run.whole_readings))
        )
    return [
        "## Figure 9: peak GPU memory by stage",
        "",
        f"From `{memory.source}`, both cards read every {memory.interval_seconds:g} s; card 0 is "
        f"the anomaly model's, `{memory.anomaly_card}`, and card 1 the judge's, "
        f"`{memory.judge_card}`. Each part's readings are the file its record names, and the "
        "wrapper's own for the whole of each run, across the gap between the two processes, are "
        "`raw/<run>.cards.csv`. A stage shorter than the interval can have no reading, so a peak "
        "here is a sample's and can miss a shorter one: the final's bench read at 0.5 s.",
        "",
        *_table(("Run", "Part", "Stage", "Card 0, MiB", "Card 1, MiB", "Readings"), rows),
        "",
    ]


def _setting_lines(runs: Sequence[OneRun]) -> list[str]:
    """Lay out the final's setting as each record read it, and what the record is made of.

    Args:
        runs: The runs.

    Returns:
        The sections' lines.
    """
    rows: list[Sequence[object]] = []
    for run in runs:
        for part in PARTS:
            record = run.records[part]
            cold = record.judge.cold
            checkpoint = record.run.checkpoint
            warm_up = record.judge.warm_up
            rows.append(
                (
                    run.name,
                    part,
                    "None" if checkpoint is None else f"`{checkpoint.sha256[:16]}...`",
                    f"{record.leak.with_corrections_in_prompt} of {record.leak.decisions}",
                    "None"
                    if cold is None
                    else f"{cold.hit_rate_percent}%, {cold.hit_rate_readings}",
                    record.specification.equals_tracked_clause_table,
                    "None"
                    if warm_up is None or warm_up.seconds is None
                    else f"{warm_up.seconds:.2f} s",
                )
            )
    each = runs[-1].records[PARTS[0]]
    server = "; ".join(f"`{key}` {value}" for key, value in sorted(each.judge.server.items()))
    head = (
        "Run",
        "Part",
        "Checkpoint",
        "Corrections in a prompt",
        "Highest hit rate, readings",
        "Clause table equals the tracked",
        "Warm-up",
    )
    return [
        "## The final's setting, as each record read it",
        "",
        *_table(head, rows),
        "",
        f"The server, as it said of itself: {server}.",
        "",
        "## What the record is made of",
        "",
        "Every file by its SHA-256, in each record under `protocol`:",
        "",
        *_table(("File", "SHA-256"), [(f"`{f.path}`", f"`{f.sha256}`") for f in each.protocol]),
        "",
    ]


def render_page(directory: Path, runs: Sequence[OneRun]) -> str:
    """Write the batch's page from its files.

    Args:
        directory: The batch's directory.
        runs: The runs, in order.

    Returns:
        The page.
    """
    return "\n".join(
        [
            *_head_lines(),
            *_digest_lines(directory),
            *_runs_lines(runs),
            *_boards_lines(runs),
            *_against_final_lines(directory, runs),
            *_sizes_lines(runs),
            *_figure_seven_lines(runs),
            *_figure_eight_lines(runs),
            *_figure_nine_lines(runs),
            *_setting_lines(runs),
        ]
    )


def _list_name(item: object, position: int) -> object:
    """Name an item of a list by what it holds: a board by its id, an area by its index.

    Args:
        item: The item.
        position: Where it stands in the list.

    Returns:
        The name to show between the brackets.
    """
    if not isinstance(item, dict):
        return position
    entry = cast("dict[str, object]", item)
    return entry.get("image_id", entry.get("index", position))


def _flattened(value: object, prefix: str = "") -> dict[str, object]:
    """Lay a record's JSON out as one value per field, boards and areas named rather than numbered.

    Args:
        value: The JSON value.
        prefix: The path so far.

    Returns:
        Each field's path and its value.
    """
    if isinstance(value, dict):
        fields: dict[str, object] = {}
        for key, item in cast("dict[str, object]", value).items():
            fields.update(_flattened(item, f"{prefix}.{key}" if prefix else key))
        return fields
    if isinstance(value, list):
        fields = {}
        for position, item in enumerate(cast("list[object]", value)):
            fields.update(_flattened(item, f"{prefix}[{_list_name(item, position)}]"))
        return fields
    return {prefix: value}


def _section(field: str) -> str:
    """Name the section of `two-runs.md` a field falls in.

    Args:
        field: The field's path.

    Returns:
        The section.
    """
    return _SECTIONS.get(re.split(r"[.\[]", field, maxsplit=1)[0], _OTHER_SECTION)


def _shown(value: object) -> str:
    """Write a value in a table's cell.

    Args:
        value: The value.

    Returns:
        The value as the record holds it, with no pipe to break the table.
    """
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_two_runs(first: OneRun, second: OneRun) -> str:
    """Write every value that differs between two runs, from the records alone.

    Args:
        first: The first run.
        second: The second.

    Returns:
        The page.
    """
    lines = [
        "# The whole batch's two runs: every value that differs",
        "",
        "Made from the records alone, field by field: `first-run.<part>.json` and `<part>.json`, "
        "and what the wrapper wrote. A field not listed reads the same in both.",
        "",
        "## The boards",
        "",
    ]
    rows: list[Sequence[object]] = []
    for part in PARTS:
        before = {line.image_id: line for line in first.records[part].observations}
        after = {line.image_id: line for line in second.records[part].observations}
        rows.append(
            (
                part,
                len(before.keys() & after.keys()),
                *(
                    sum(
                        getattr(before[image], field) != getattr(after[image], field)
                        for image in before.keys() & after.keys()
                    )
                    for field in _BOARD_FIELDS
                ),
            )
        )
    lines += [*_table(("Part", "Boards in both", *_BOARD_FIELDS), rows), ""]

    lines += ["## The whole run's wall clock, the wrapper's", ""]
    wall = [
        ("the whole run", wall_clock_seconds(first.wrapper), wall_clock_seconds(second.wrapper))
    ] + [
        (part, wall_clock_seconds(first.parts[part]), wall_clock_seconds(second.parts[part]))
        for part in PARTS
    ]
    lines += [
        *_table(("Step", "Run 1, seconds", "Run 2, seconds"), wall),
        "",
    ]

    differing: dict[str, dict[str, list[tuple[str, object, object]]]] = {}
    tally: dict[tuple[str, str], list[int]] = {}
    for part in PARTS:
        before = _flattened(cast("object", json.loads(first.records[part].model_dump_json())))
        after = _flattened(cast("object", json.loads(second.records[part].model_dump_json())))
        for field in sorted(before.keys() | after.keys()):
            section = _section(field)
            counts = tally.setdefault((part, section), [0, 0])
            counts[0] += 1
            if before.get(field) != after.get(field):
                counts[1] += 1
                differing.setdefault(section, {}).setdefault(part, []).append(
                    (field, before.get(field), after.get(field))
                )

    lines += ["## The fields of each part's record", ""]
    lines += [
        *_table(
            ("Part", "Part of the record", "Fields", "Fields that differ"),
            [
                (part, section, counts[0], counts[1])
                for (part, section), counts in sorted(tally.items())
            ],
        ),
        "",
    ]
    for section in sorted(differing):
        lines += [f"## {section}", ""]
        for part, values in sorted(differing[section].items()):
            lines += [f"### {part}", ""]
            lines += [
                *_table(
                    ("Field", "Run 1", "Run 2"),
                    [(f"`{f}`", _shown(a), _shown(b)) for f, a, b in values],
                ),
                "",
            ]
    return "\n".join(lines)


def write_pages(directory: Path) -> tuple[Path, Path]:
    """Make the page and `two-runs.md` from the batch's files.

    Args:
        directory: The batch's directory.

    Returns:
        The two files' paths.
    """
    first = read_run(directory, RUNS[0], "first-run.")
    second = read_run(directory, RUNS[1], "")
    page = directory / PAGE_NAME
    page.write_text(render_page(directory, (first, second)), encoding="utf-8")
    two = directory / TWO_RUNS_NAME
    two.write_text(render_two_runs(first, second), encoding="utf-8")
    return page, two


def main() -> None:
    """Make the page and `two-runs.md` of the directory given on the command line."""
    parser = argparse.ArgumentParser(description="Make the whole batch's page from its files.")
    parser.add_argument("directory", type=Path, help="The batch's directory.")
    for path in write_pages(parser.parse_args().directory):
        print(path)


if __name__ == "__main__":
    main()
