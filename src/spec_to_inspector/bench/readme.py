"""The bench's figures as a page: `results/stage1/README.md`, written from a record.

The page is what the deck quotes from, so every proportion on it carries its
count, its N and its 95% Wilson score interval, and the page names the date,
the command and the protocol. It is written by the command and never by hand:
a figure that is wrong here is wrong in the record.
"""

from collections.abc import Iterable, Mapping, Sequence

from spec_to_inspector.bench.mapping import CLAUSE_MAPPING
from spec_to_inspector.bench.observe import Citation
from spec_to_inspector.bench.record import BenchRecord, Repeat, StageMemory
from spec_to_inspector.bench.score import Accuracy, Confusion, Dispositions, FalseAlarms
from spec_to_inspector.bench.wilson import Proportion
from spec_to_inspector.judge.timing import Spread

_NO_CITATION = tuple(state.value for state in Citation if state is not Citation.CITED)
_NONE = "none"


def _percent(rate: float | None) -> str:
    """Write a fraction of 1 as a percentage.

    Args:
        rate: The fraction, or None where there is none.

    Returns:
        The percentage to one decimal, or a dash.
    """
    return "-" if rate is None else f"{rate * 100:.1f}%"


def _share(proportion: Proportion) -> str:
    """Write a proportion as its percentage and its count.

    Args:
        proportion: The proportion.

    Returns:
        Such as `60.0% (81 of 135)`; the count alone when N is zero.
    """
    counted = f"{proportion.count} of {proportion.n}"
    return counted if proportion.rate is None else f"{_percent(proportion.rate)} ({counted})"


def _interval(proportion: Proportion) -> str:
    """Write a proportion's 95% interval.

    Args:
        proportion: The proportion.

    Returns:
        Such as `51.6% to 67.9%`, or a dash when N is zero.
    """
    if proportion.low is None or proportion.high is None:
        return "-"
    return f"{_percent(proportion.low)} to {_percent(proportion.high)}"


def _seconds(spread: Spread | None) -> str:
    """Write a spread of seconds as its median and 95th percentile.

    Args:
        spread: The spread, or None where nothing was measured.

    Returns:
        Such as `3.30 s (p95 3.44 s, n 250)`, or a dash.
    """
    if spread is None:
        return "-"
    return f"{spread.p50:.2f} s (p95 {spread.p95:.2f} s, n {spread.n})"


def _mib(value: int | None) -> str:
    """Write a memory reading.

    Args:
        value: MiB, or None where the process was not on the card.

    Returns:
        Such as `8,764 MiB`, or `not read`.
    """
    return "not read" if value is None else f"{value:,} MiB"


def _counts(counts: Mapping[str, int]) -> str:
    """Write counts by name on one line.

    Args:
        counts: The counts.

    Returns:
        Such as `reject 5, accept 1`, or `none`.
    """
    return ", ".join(f"{name} {count}" for name, count in counts.items()) or _NONE


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """Lay rows out as a Markdown table.

    Args:
        header: The column titles.
        rows: The rows, each as long as the header.

    Returns:
        The table's lines.
    """
    lines = [f"| {' | '.join(header)} |", f"| {' | '.join('---' for _ in header)} |"]
    lines.extend(f"| {' | '.join(row)} |" for row in rows)
    return lines


def _accuracy_rows(name: str, accuracy: Accuracy) -> list[list[str]]:
    """Give a figure's rows: the parts together, then each part.

    Args:
        name: The figure's name.
        accuracy: The figure.

    Returns:
        One row for all parts and one per part.
    """
    rows = [[name, _share(accuracy.all), str(accuracy.all.n), _interval(accuracy.all)]]
    rows.extend(
        [f"{name}, {part} only", _share(found), str(found.n), _interval(found)]
        for part, found in accuracy.by_part.items()
    )
    return rows


def _confusion_tables(title: str, confusion: Confusion) -> list[str]:
    """Lay a confusion table out, one Markdown table per part.

    Args:
        title: What the rows are.
        confusion: The counts.

    Returns:
        The lines; columns in the mapping table's order, then the columns
        for an image with no citation.
    """
    lines: list[str] = []
    for part, table in confusion.items():
        seen = {column for columns in table.values() for column in columns}
        types = [row.visa_type for row in CLAUSE_MAPPING if row.part == part]
        columns = [name for name in (*types, *_NO_CITATION) if name in seen]
        columns += sorted(seen - set(columns))
        ordered = [name for name in types if name in table]
        lines += [f"{part}, {title}:", ""]
        lines += _table(
            ["Expected \\ cited", *columns, "Images"],
            (
                [
                    f"**{expected}**",
                    *(str(table[expected].get(column, 0)) for column in columns),
                    str(sum(table[expected].values())),
                ]
                for expected in ordered
            ),
        )
        lines.append("")
    return lines


def _disposition_lines(dispositions: Dispositions, boards: str) -> list[str]:
    """Write what became of some boards and their areas, by cause.

    Args:
        dispositions: The breakdown.
        boards: What the boards are, in words.

    Returns:
        The lines.
    """
    board, area = dispositions.board_needs_review, dispositions.area_needs_review
    return [
        f"- Boards: {dispositions.boards} {boards}; {dispositions.not_flagged} not flagged "
        f"by the anomaly model; of the flagged, {_counts(dispositions.board_outcomes)}.",
        f"- Boards referred for review: {_share(board)}, 95% interval {_interval(board)}. "
        f"By cause: {_counts(dispositions.board_review_causes)}.",
        f"- Areas put to the judge on those boards: {dispositions.areas}; "
        f"{_counts(dispositions.area_outcomes)}.",
        f"- Areas referred for review: {_share(area)}, 95% interval {_interval(area)}. "
        f"By cause: {_counts(dispositions.area_review_causes)}.",
    ]


def _false_alarm_row(name: str, alarms: FalseAlarms) -> list[str]:
    """Give one row of the false-alarm table.

    Args:
        name: The part, or all parts.
        alarms: The good boards' counts.

    Returns:
        The row.
    """
    return [
        name,
        str(alarms.flagged.n),
        _share(alarms.flagged),
        f"{_share(alarms.rejected)}, {_interval(alarms.rejected)}",
        _share(alarms.referred),
        _share(alarms.accepted_after_judging),
    ]


def _memory_row(stage: str, process: str, memory: StageMemory) -> list[str]:
    """Give one row of the memory table.

    Args:
        stage: The stage.
        process: Whose process the first figure is.
        memory: The readings.

    Returns:
        The row.
    """
    return [
        stage,
        f"{_mib(memory.process_peak_mib)} ({process})",
        _mib(memory.card_peak_mib),
        _mib(memory.card_before_mib),
        f"{memory.samples} at {memory.interval_seconds:g} s",
    ]


def _repeat_lines(repeat: Repeat | None) -> list[str]:
    """Write how the run compares with the run before it.

    Args:
        repeat: The comparison, or None where there was no earlier run of
            the same making.

    Returns:
        The lines.
    """
    if repeat is None:
        return [
            "This file holds one run. Run the command again and the next record says how many",
            "of its answers differ from this one.",
        ]
    figures = (
        "Every counted figure of the protocol is equal in the two runs."
        if repeat.figures_equal
        else "**The counted figures are not all equal in the two runs**: the earlier run's are "
        "kept in `bench.json` under `repeat.previous_scores`, and both are to be reported."
    )
    differing = ", ".join(repeat.differing_images) or _NONE
    return [
        f"This run was compared with the run of the same command before it "
        f"({repeat.previous_measured_at}), image by image:",
        "",
        f"- {repeat.images_compared} images in both runs: {repeat.flag_differs} flagged in one "
        f"and not the other, {repeat.score_differs} with another anomaly score, "
        f"{repeat.outcome_differs} with another board outcome.",
        f"- {repeat.areas_compared} images answered on region 1 in both runs: "
        f"{repeat.heading_differs} with another heading cited, {repeat.class_differs} with "
        f"another class named, {repeat.sentence_differs} with another sentence.",
        f"- Images that differ in anything but the sentence: {differing}.",
        f"- {figures}",
    ]


def _beside_lines(record: BenchRecord, beside: BenchRecord) -> list[str]:
    """Compare the run with a run of the same command against another server setting.

    Args:
        record: The run the page is about.
        beside: The other run.

    Returns:
        The lines.
    """

    def column(run: BenchRecord) -> list[str]:
        scores, times = run.scores, run.times
        return [
            _share(scores.headline.strict.all),
            _interval(scores.headline.strict.all),
            _share(scores.lenient.all),
            _share(scores.per_region.all),
            _share(scores.good.all.rejected),
            _share(scores.anomalous.board_needs_review),
            _seconds(times.vlm_seconds_per_area),
            _seconds(times.flagged_image_seconds),
            _mib(run.judge_memory.process_peak_mib),
        ]

    names = [
        "Strict, single-defect images",
        "Its 95% interval",
        "Lenient, multi-defect images",
        "Per region",
        "Good boards rejected",
        "Anomalous boards referred",
        "The VLM's answer to one area, cold",
        "A flagged image, end to end",
        "VLM server, peak GPU memory",
    ]
    shipped, other = column(record), column(beside)
    return [
        "The same command against the same server started with another minimum of tokens an",
        "image, the least the server gives a small crop (`--image-min-tokens`), as",
        f"`eval/PROTOCOL.md` declared in advance. The other run was made on "
        f"{beside.measured_on}{' and is partial' if beside.partial else ''}. The headline is",
        "this page's setting whichever is higher.",
        "",
        *_table(
            [
                "Figure",
                f"Image tokens: {record.judge.image_min_tokens} (this page)",
                f"Image tokens: {beside.judge.image_min_tokens}",
            ],
            (
                [name, mine, theirs]
                for name, mine, theirs in zip(names, shipped, other, strict=True)
            ),
        ),
    ]


def summary_lines(record: BenchRecord) -> list[str]:
    """Give a run's figures in a few lines, for the terminal.

    Args:
        record: The run.

    Returns:
        The lines: the three accuracies, the false rejects, and the repeat.
    """
    scores, labels = record.scores, record.labels
    strict, good = scores.headline.strict.all, scores.good.all.rejected
    lines = [
        ("Partial run, not the protocol's figures. " if record.partial else "")
        + f"Clause-citation accuracy, strict, {labels.single_defect} single-defect images: "
        f"{_share(strict)}, 95% interval {_interval(strict)}",
        f"Lenient, {labels.multi_defect} multi-defect images: {_share(scores.lenient.all)}, "
        f"95% interval {_interval(scores.lenient.all)}",
        f"Per region, one defect type under region 1: {_share(scores.per_region.all)}, "
        f"95% interval {_interval(scores.per_region.all)}",
        f"Good boards rejected: {_share(good)}, 95% interval {_interval(good)}; "
        f"flagged by the anomaly model: {_share(scores.good.all.flagged)}",
        f"Corrections in a prompt: {record.leak.with_corrections_in_prompt} of "
        f"{record.leak.decisions} decisions",
    ]
    repeat = record.repeat
    if repeat is not None:
        lines.append(
            f"Against the run of {repeat.previous_measured_at}: {repeat.heading_differs} of "
            f"{repeat.areas_compared} images cite another heading, {repeat.class_differs} name "
            f"another class, {repeat.sentence_differs} give another sentence; the figures are "
            + ("equal" if repeat.figures_equal else "NOT equal")
        )
    return lines


def render_readme(record: BenchRecord, *, beside: BenchRecord | None = None) -> str:
    """Write the page of a run's figures.

    Args:
        record: The run.
        beside: A run of the same command against another server setting, to
            compare with; None for no comparison.

    Returns:
        The page, as Markdown.
    """
    scores, times, judge = record.scores, record.times, record.judge
    headline, good, inspector = scores.headline, scores.good, record.inspector
    labels = record.labels
    server = ", ".join(f"{key} {value}" for key, value in judge.server.items()) or "not reported"
    one_part = next(iter(inspector.minutes_by_part.values()))
    fit = ", ".join(f"{part} {seconds:.0f} s" for part, seconds in inspector.fit_seconds.items())

    lines = [
        "# Stage I: what the laptop prototype measured",
        "",
        f"Written by `{' '.join(record.command)}` on {record.measured_on} ({record.measured_at}).",
        "Not edited by hand: a figure that is wrong here is wrong in `bench.json`, and the",
        "remedy is to run the command again.",
        "",
        f"The figures follow `{record.protocol.path}` (SHA-256 `{record.protocol.sha256[:16]}`),",
        "which was written before the run. Every proportion is a count of its N with the 95%",
        "Wilson score interval. Nothing here is a held-out figure: see the last section.",
        "",
    ]
    if record.partial:
        lines += [
            f"**This is a partial run** ({labels.images} labelled images"
            + ("" if record.limit is None else f", the first {record.limit} of each kind per part")
            + f"; parts {', '.join(record.parts)}). Its figures are not the protocol's and are "
            "not for the deck.",
            "",
        ]
    lines += [
        "## The figures the deck quotes",
        "",
        *_table(
            ["Figure", "Value", "N", "95% interval"],
            [
                *_accuracy_rows(
                    "Clause-citation accuracy, strict, single-defect images", headline.strict
                ),
                *_accuracy_rows(
                    "Clause-citation accuracy, lenient, multi-defect images", scores.lenient
                )[:1],
                *_accuracy_rows(
                    "Clause-citation accuracy per region, one defect type under region 1",
                    scores.per_region,
                )[:1],
                [
                    "Anomalous boards referred for review",
                    _share(scores.anomalous.board_needs_review),
                    str(scores.anomalous.board_needs_review.n),
                    _interval(scores.anomalous.board_needs_review),
                ],
                [
                    "Good boards rejected (false rejects)",
                    _share(good.all.rejected),
                    str(good.all.rejected.n),
                    _interval(good.all.rejected),
                ],
                [
                    "Good boards flagged by the anomaly model",
                    _share(good.all.flagged),
                    str(good.all.flagged.n),
                    _interval(good.all.flagged),
                ],
            ],
        ),
        "",
        *_table(
            ["Figure", "Value"],
            [
                ["A flagged image, end to end, median", _seconds(times.flagged_image_seconds)],
                [
                    "The VLM's answer to one flagged area, cold, median",
                    _seconds(times.vlm_seconds_per_area),
                ],
                [
                    "From specification to a working inspector, one part",
                    f"{one_part:.1f} min (parse {inspector.parse_seconds:.1f} s measured here; "
                    f"fit as recorded at training: {fit})",
                ],
                [
                    "From specification to a working inspector, all parts in turn",
                    f"{inspector.minutes_all_parts:.1f} min",
                ],
                [
                    "Peak GPU memory, VLM server while judging",
                    _mib(record.judge_memory.process_peak_mib),
                ],
                [
                    "Peak GPU memory, the card while judging",
                    _mib(record.judge_memory.card_peak_mib),
                ],
            ],
        ),
        "",
        "The lenient figure counts a citation of any of the image's defect types and is never",
        "pooled with the strict one. The false rejects stand beside the accuracy and are never",
        "folded into it.",
        "",
        "## How it was run",
        "",
        f"- The labelled set: `{labels.file.path}` (SHA-256 `{labels.file.sha256[:16]}`), "
        f"{labels.images} anomalous test images: {labels.single_defect} single-defect, "
        f"{labels.multi_defect} multi-defect. Labels are VisA's defect annotation mapped to "
        "clauses by the written table `eval/clause_mapping.md`.",
        f"- The specification: `{record.specification.pdf.path}`, parsed in "
        f"{record.specification.parse_seconds:.1f} s into {record.specification.clauses} clauses "
        f"under {record.specification.headings} numbered headings, equal to the tracked "
        f"`{record.specification.clause_table.path}`.",
        f"- The judge: `{judge.model}` at `{judge.url}` ({server}); image minimum "
        f"{judge.image_min_tokens} tokens; GPU {judge.gpu or 'not read'}; up to "
        f"{judge.max_regions} areas an image, stopping at the first reject.",
        "- Every question asked cold (`cache_prompt` false), so the answers repeat.",
        f"- The corrections store empty: {record.leak.with_corrections_in_prompt} of "
        f"{record.leak.decisions} decisions had a correction in a prompt "
        "(`decision.corrected.in_prompt`).",
        "- The anomaly models are the trained ones, not retrained: "
        + "; ".join(
            f"{part} trained {run.model_trained_at}, image threshold {run.image_threshold:.3f}"
            + (" (chosen on the test split)" if run.thresholds_tuned_on_test else "")
            for part, run in record.runs.items()
        )
        + ".",
        "",
        "## 1. The headline: strict accuracy on the single-defect images",
        "",
        "The citation is the heading id the judge cited on region 1, the most anomalous area.",
        'An image with no citation (not flagged, not asked, no valid answer, or "no clause',
        'applies") counts as wrong.',
        "",
        *_table(
            ["Figure", "Value", "N", "95% interval"],
            [
                *_accuracy_rows("Strict accuracy", headline.strict),
                *_accuracy_rows("Flagged by the anomaly model", headline.flagged),
                *_accuracy_rows("Region 1 lies on the labelled defect", headline.on_defect),
                *_accuracy_rows(
                    "Strict accuracy, flagged images only (conditional)",
                    headline.strict_given_flagged,
                ),
                *_accuracy_rows(
                    "Strict accuracy, region 1 on the defect only (conditional)",
                    headline.strict_given_on_defect,
                ),
            ],
        ),
        "",
        "For the correct citations, what code then did (the row is a measurement's outcome, not",
        "what is scored):",
        "",
        f"- Row of the clause table applied: {_counts(headline.rows_applied)}.",
        f"- Outcome of region 1: {_counts(headline.region1_outcomes)}.",
        "",
        "## 2. The lenient figure: the multi-defect images",
        "",
        *_table(
            ["Figure", "Value", "N", "95% interval"],
            _accuracy_rows("Lenient accuracy", scores.lenient),
        ),
        "",
        "## 3. The per-region figure",
        "",
        "Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,",
        "scored against that type's heading.",
        "",
        *_table(
            ["Figure", "Value", "N", "95% interval"],
            _accuracy_rows("Per-region accuracy", scores.per_region),
        ),
        "",
        "## 4. The confusion tables",
        "",
        "Rows are the expected defect type; columns are the type of the heading cited, or why",
        "there is no citation.",
        "",
        *_confusion_tables("single-defect images", scores.confusion_single),
        *_confusion_tables(
            "images with one type under region 1, by that type", scores.confusion_region
        ),
        f"Citations on labelled images whose named class is not the class of the heading cited: "
        f"{scores.class_not_of_heading}.",
        "",
        "## 5. Needs review, by cause, on the anomalous boards",
        "",
        *_disposition_lines(scores.anomalous, "anomalous"),
        "",
        "## 6. False alarms on the good boards",
        "",
        *_table(
            [
                "Part",
                "Good boards",
                "Flagged",
                "Rejected (false rejects), 95% interval",
                "Referred",
                "Accepted after judging",
            ],
            [
                _false_alarm_row("all", good.all),
                *(_false_alarm_row(part, alarms) for part, alarms in good.by_part.items()),
            ],
        ),
        "",
        "- What the judge cited on region 1 of the flagged good boards: "
        f"{_counts(good.all.citations)}.",
        *_disposition_lines(good.all.dispositions, "good"),
        "",
        "## 7. Time per image, by stage",
        "",
        *_table(
            ["Stage", "Time"],
            [
                [
                    "Parse the specification (once per specification; includes loading the "
                    "parser's models)",
                    f"{times.parse_seconds:.1f} s",
                ],
                *(
                    [
                        f"Anomaly model, {part}, per image (batch {record.runs[part].batch_size}; "
                        "scoring and writing maps, masks and crops)",
                        f"{seconds * 1000:.0f} ms",
                    ]
                    for part, seconds in times.anomaly_seconds_per_image.items()
                ),
                [
                    "Measure and draw a flagged image's areas, the rule, the decision",
                    _seconds(times.measure_and_draw_seconds),
                ],
                ["The VLM's answer to one area, cold", _seconds(times.vlm_seconds_per_area)],
                [
                    "The VLM's answers to one flagged image",
                    _seconds(times.vlm_seconds_per_flagged_image),
                ],
                ["A flagged image, end to end", _seconds(times.flagged_image_seconds)],
            ],
        ),
        "",
        f"{times.flagged_images} flagged images, {times.areas_asked} areas asked"
        + (
            ""
            if times.areas_per_flagged_image is None
            else f" ({times.areas_per_flagged_image:.2f} an image)"
        )
        + f"; the judge's stage took {times.judge_stage_seconds:.0f} s in all. An image that is "
        "not flagged costs the anomaly model's time only. Prompt tokens, median: "
        + ("-" if times.prompt_tokens is None else f"{times.prompt_tokens.p50:,.0f}")
        + "; answer tokens, median: "
        + ("-" if times.completion_tokens is None else f"{times.completion_tokens.p50:.0f}")
        + "; output rate, median: "
        + (
            "-"
            if times.output_tokens_per_second is None
            else f"{times.output_tokens_per_second.p50:.1f} tokens a second"
        )
        + ".",
        "",
        "## 8. Minutes from specification to a working inspector",
        "",
        *_table(
            ["Part", "Parse, measured in this run", "Fit, as recorded at training", "Together"],
            [
                *(
                    [
                        part,
                        f"{inspector.parse_seconds:.1f} s",
                        f"{inspector.fit_seconds[part]:.0f} s",
                        f"{minutes:.1f} min",
                    ]
                    for part, minutes in inspector.minutes_by_part.items()
                ),
                [
                    "all parts, one after another",
                    f"{inspector.parse_seconds:.1f} s",
                    f"{sum(inspector.fit_seconds.values()):.0f} s",
                    f"{inspector.minutes_all_parts:.1f} min",
                ],
            ],
        ),
        "",
        "Training is not repeated by the bench: the fit time is the one in each model's own",
        "training record. A rebuilt model has the same thresholds to the last digit.",
        "",
        "## 9. Peak GPU memory, by stage",
        "",
        *_table(
            ["Stage", "The stage's own process", "The card", "The card before", "Readings"],
            [
                *(
                    _memory_row(f"Anomaly model scoring, {part}", "the bench's process", run.memory)
                    for part, run in record.runs.items()
                ),
                _memory_row("Judging", "the VLM server", record.judge_memory),
            ],
        ),
        "",
        "Read from `nvidia-smi` for the process concerned. While the anomaly model scores, the",
        "VLM server is resident too, so the card's figure in those rows is both together."
        + "".join(
            f" Training {part} peaked at {run.train_peak_allocated_mib:,.0f} MiB allocated, as "
            "recorded then."
            for part, run in record.runs.items()
            if run.train_peak_allocated_mib is not None
        ),
        "",
        "## Reproducing",
        "",
        "```",
        "uv sync",
        "uv run spec-to-inspector data fetch",
        "scripts/serve_vlm.sh start",
        "uv run spec-to-inspector bench",
        "scripts/serve_vlm.sh stop",
        "```",
        "",
        *_repeat_lines(record.repeat),
        "",
    ]
    if beside is not None:
        lines += ["## The other image setting", "", *_beside_lines(record, beside), ""]
    lines += [
        "## What these figures are not",
        "",
        "- Not held out. VisA's PCB test split is the only labelled data; the anomaly model's",
        "  thresholds were chosen on it, and the judge's prompt was written with sight of some",
        "  of its images.",
        "- Not a figure for the corrections loop: the store is empty throughout.",
        "- One demonstration specification, one model at one quantisation, one laptop GPU.",
        "- The labels are VisA's annotation mapped to clauses by a written table; 20 rows are",
        "  for the operator to check by hand (`eval/spot-check-2026-10-11.md`).",
        "",
        "## Files",
        "",
        "- `bench.json`: this run, whole: every figure with its N and interval, and one line per",
        "  image from which any of them can be counted again.",
        "- `anomaly.json`, `spec.json`, `judge.json`, `corrections.json` and their siblings: the",
        "  earlier units' own measurements.",
        "",
    ]
    return "\n".join(lines)
