"""The one entry point: `spec-to-inspector <verb>`."""

import signal
import sys
import time
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Annotated, NoReturn

import typer
from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from spec_to_inspector.datasets.visa import (
    MANIFEST_NAME,
    PUBLISHED_COUNTS,
    FetchResult,
    VisaFetchError,
    VisaVerificationError,
    fetch_visa,
)
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.extract import SpecificationError
from spec_to_inspector.spec.limits import Comparison
from spec_to_inspector.spec.pdf import PdfError, read_pdf
from spec_to_inspector.spec.schema import Specification, read_clause_table, write_clause_table
from spec_to_inspector.spec.summary import summarise
from spec_to_inspector.spec.tokens import TokenizerError

app = typer.Typer(
    name="spec-to-inspector",
    help="Turn a PCB workmanship specification into a visual inspector that cites its clauses.",
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(help="Fetch and verify the VisA PCB data.", no_args_is_help=True)
app.add_typer(data_app, name="data")

out = Console()
err = Console(stderr=True)

TRAIN_BACKBONE = "wide_resnet50_2"
"""The product's PatchCore backbone, Anomalib's default; kept here so the anomaly package,
which takes seconds to import, is loaded by the `train` verb alone."""


def _not_built(verb: str, unit: str) -> NoReturn:
    """Report that a verb is a stub and exit non-zero.

    Args:
        verb: The verb invoked.
        unit: The Stage I unit that builds it.

    Raises:
        typer.Exit: Always, with code 1.
    """
    err.print(f"spec-to-inspector {verb}: not built yet; unit {unit} builds it.")
    raise typer.Exit(code=1)


@contextmanager
def _terminate_cleanly() -> Generator[None]:
    """Turn SIGTERM into SystemExit for the duration, so cleanup code runs on a kill.

    Yields:
        Nothing; the previous handler is restored on exit.
    """

    def _exit(signum: int, frame: FrameType | None) -> NoReturn:
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, _exit)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


class _ProgressReport:
    """Progress of a stream: a live bar on a terminal, a plain line per tenth elsewhere."""

    def __init__(self, progress: Progress, task: TaskID, console: Console) -> None:
        """Bind the report to its bar and console.

        Args:
            progress: The live bar, shown only on a terminal.
            task: The bar's task.
            console: Where plain lines go when there is no terminal.
        """
        self._progress = progress
        self._task = task
        self._console = console
        self._next_tenth = 1

    def __call__(self, done: int, total: int | None) -> None:
        """Record the bytes received so far.

        Args:
            done: Bytes received.
            total: The stream's size, if known.
        """
        self._progress.update(self._task, completed=done, total=total)
        if self._console.is_terminal or not total:
            return
        while self._next_tenth <= 10 and done * 10 >= total * self._next_tenth:
            self._console.print(
                f"Received {done / 1e6:,.0f} of {total / 1e6:,.0f} MB ({self._next_tenth * 10}%)",
                markup=False,
                highlight=False,
                soft_wrap=True,
            )
            self._next_tenth += 1


def _counts_table(result: FetchResult) -> Table:
    """Lay out the verified counts per category, narrow enough for an 80-column log.

    Args:
        result: The fetch's result.

    Returns:
        A table with one row per category.
    """
    table = Table(
        title=f"VisA, verified against the published counts ({result.path})",
        box=box.SIMPLE_HEAD,
    )
    table.add_column("Category")
    for column in (
        "Normal",
        "Anomalous",
        "Masks",
        "Train",
        "Test\nnormal",
        "Test\nanomalous",
        "Multi-\ndefect",
    ):
        table.add_column(column, justify="right")
    for name, counts in result.manifest.categories.items():
        table.add_row(
            name,
            *(
                str(n)
                for n in (
                    counts.normal,
                    counts.anomalous,
                    counts.masks,
                    counts.train_normal,
                    counts.test_normal,
                    counts.test_anomalous,
                    counts.multi_defect,
                )
            ),
        )
    return table


def _defect_lines(result: FetchResult) -> list[str]:
    """List each category's defect types with their image counts, most common first.

    Args:
        result: The fetch's result.

    Returns:
        One line per category.
    """
    return [
        f"{name} defect types: "
        + ", ".join(f"{kind} {n}" for kind, n in counts.defect_types.items())
        for name, counts in result.manifest.categories.items()
    ]


@data_app.command("fetch")
def data_fetch(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Stream afresh even if a manifest is present; replaces everything under "
            "the dataset directory, Anomalib's split copy included.",
        ),
    ] = False,
) -> None:
    """Stream VisA through tar, keep the four PCB categories, and verify the published counts.

    The tarball is never stored. With a manifest already present, nothing is
    downloaded: the kept files are recounted and rehashed instead.
    """
    settings = Settings()
    dest = settings.visa_dir
    streaming = force or not (dest / MANIFEST_NAME).is_file()
    if streaming:
        err.print(f"Streaming {settings.visa_url} through tar into {dest}", soft_wrap=True)
    else:
        err.print(f"Re-verifying {dest} against its manifest", soft_wrap=True)
    progress = Progress(
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=err,
        disable=not streaming,
    )
    report = _ProgressReport(progress, progress.add_task("VisA", total=None), err)
    try:
        with _terminate_cleanly(), progress:
            result = fetch_visa(
                dest,
                url=settings.visa_url,
                force=force,
                on_progress=report,
            )
    except (VisaFetchError, VisaVerificationError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error

    out.print(_counts_table(result))
    for line in _defect_lines(result):
        out.print(line, markup=False, highlight=False, soft_wrap=True)
    source, tree = result.manifest.source, result.manifest.tree
    verb = "Streamed" if result.downloaded else "Re-verified"
    out.print(
        f"{verb}: {tree.files} files, {tree.bytes / 1024**2:.0f} MiB kept from "
        f"{source.bytes:,} bytes (sha256 {source.sha256}).",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    out.print(f"Manifest: {dest / MANIFEST_NAME}", markup=False, highlight=False, soft_wrap=True)


def _clause_table(specification: Specification) -> Table:
    """Lay out the clause table, one row per clause.

    Args:
        specification: The parsed specification.

    Returns:
        A table of every clause with its part, class, zone, limit, disposition and page.
    """
    table = Table(title=specification.title, box=box.SIMPLE_HEAD)
    for column in ("Clause", "Title", "Part", "Defect class", "Zone", "Limit", "Disposition"):
        table.add_column(column)
    table.add_column("Page", justify="right")
    for clause in specification.clauses:
        limit = (
            "any size"
            if clause.comparison is Comparison.UNCONDITIONAL
            else f"{clause.comparison.value} {clause.limit:g} {clause.unit}"
        )
        table.add_row(
            clause.id,
            clause.title,
            clause.category,
            clause.defect_class,
            clause.zone,
            limit,
            clause.disposition.value,
            str(clause.page),
        )
    return table


@app.command()
def parse(
    pdf: Annotated[Path, typer.Argument(help="The specification, a born-digital PDF.")],
    out_path: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Where the clause table goes; beside the PDF, as <name>.clauses.json, by default.",
        ),
    ] = None,
    results: Annotated[
        Path | None,
        typer.Option(
            "--results",
            help="Also write the measured summary (pages, clauses, tokens, parse time) "
            "to this JSON file.",
        ),
    ] = None,
) -> None:
    """Parse a specification PDF into its clause table.

    docling reads the PDF on the CPU with heading levels on; the clauses,
    zones and calibrations are extracted, validated and written as JSON; a
    summary line gives the pages, the clauses and the document's size in the
    judge's tokens.
    """
    settings = Settings()
    started = time.perf_counter()
    try:
        parsed = read_pdf(pdf, artifacts_dir=settings.docling_artifacts_dir)
        specification = parsed.specification()
    except (PdfError, SpecificationError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error
    seconds = time.perf_counter() - started
    target = out_path if out_path is not None else pdf.with_suffix(".clauses.json")
    write_clause_table(specification, target)

    out.print(_clause_table(specification))
    headings = len({clause.heading_id for clause in specification.clauses})
    counted = f"{specification.pages} pages, {len(specification.clauses)} clauses under "
    counted += f"{headings} numbered headings"
    try:
        summary = summarise(pdf, parsed, specification, parse_seconds=seconds)
    except TokenizerError as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        summary = None
    tokens = (
        f"{summary.document_tokens:,} tokens ({summary.tokenizer})"
        if summary is not None
        else "tokens not counted"
    )
    out.print(
        f"Parsed {pdf}: {counted}, {tokens}, {seconds:.1f} s on the CPU.",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    out.print(f"Clause table: {target}", markup=False, highlight=False, soft_wrap=True)
    if results is not None:
        if summary is None:
            err.print(f"The summary was not written to {results}: tokens could not be counted.")
            raise typer.Exit(code=1)
        summary.write(results)
        out.print(f"Summary: {results}", markup=False, highlight=False, soft_wrap=True)


@app.command()
def train(
    category: Annotated[
        list[str] | None,
        typer.Option(
            "--category",
            "-c",
            help="A VisA PCB category to train: pcb1, pcb2, pcb3 or pcb4. May be repeated.",
        ),
    ] = None,
    all_categories: Annotated[
        bool, typer.Option("--all", help="Train the four PCB categories, pcb1 to pcb4.")
    ] = False,
    models_dir: Annotated[
        Path | None,
        typer.Option(
            "--models-dir",
            help="The output root for trained models; each lands in "
            "<models-dir>/patchcore/<category>/. Defaults to the settings' models directory.",
        ),
    ] = None,
    runs_dir: Annotated[
        Path | None,
        typer.Option(
            "--runs-dir",
            help="The output root for inference; the test split lands in "
            "<runs-dir>/<category>/test/. Defaults to the settings' runs directory.",
        ),
    ] = None,
    reuse: Annotated[
        bool,
        typer.Option("--reuse", help="Keep a model already on disk instead of training it again."),
    ] = False,
    infer: Annotated[
        bool,
        typer.Option(
            "--infer/--no-infer",
            help="Score the category's test split and write, per image, the score, the anomaly "
            "map, the thresholded mask and the region crops.",
        ),
    ] = True,
    bench: Annotated[
        bool,
        typer.Option(
            "--bench",
            help="Measure inference images per second and peak GPU memory at batch 1 and "
            "batch 16 on the test split, into <runs-dir>/<category>/bench.json.",
        ),
    ] = False,
    results_path: Annotated[
        Path | None,
        typer.Option(
            "--results",
            help="Collect every chosen category's figures from disk into this JSON file, "
            "such as results/stage1/anomaly.json.",
        ),
    ] = None,
    seed: Annotated[
        int,
        typer.Option("--seed", help="The seed for the coreset's random projection and first pick."),
    ] = 0,
    backbone: Annotated[
        str,
        typer.Option(
            "--backbone",
            help="The feature extractor, as timm names it. Another than the default is for "
            "comparison only and needs its own --models-dir.",
        ),
    ] = TRAIN_BACKBONE,
) -> None:
    """Train the anomaly model on good boards of a category, and score its test split.

    PatchCore through Anomalib, at 256 px, on the category's normal training
    images; the thresholds are Anomalib's adaptive F1 thresholds. Needs the
    CUDA GPU and the data from `spec-to-inspector data fetch`.
    """
    known = tuple(PUBLISHED_COUNTS)
    if all_categories == bool(category):
        raise typer.BadParameter(
            "give --category (once or more) or --all, not both and not neither"
        )
    chosen = known if all_categories else tuple(dict.fromkeys(category or ()))
    unknown = [name for name in chosen if name not in known]
    if unknown:
        raise typer.BadParameter(
            f"unknown category {', '.join(unknown)}; the PCB categories are {', '.join(known)}",
            param_hint="--category",
        )

    settings = Settings()
    models_root = models_dir or settings.models_dir
    runs_root = runs_dir or settings.runs_dir
    if backbone != TRAIN_BACKBONE and models_root.resolve() == settings.models_dir.resolve():
        raise typer.BadParameter(
            f"a backbone other than {TRAIN_BACKBONE} is for comparison: give it a --models-dir "
            f"of its own, not {settings.models_dir}, so the product's models are not replaced",
            param_hint="--backbone",
        )

    # Anomalib takes about ten seconds to import, so it is loaded for this verb only; its
    # dependencies' import-time deprecation notices are not the user's to act on.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        from spec_to_inspector.anomaly import console, pipeline, results  # noqa: PLC0415

    outcomes: list[pipeline.CategoryOutcome] = []
    try:
        with _terminate_cleanly():
            for name in chosen:
                err.print(
                    f"{name}: "
                    + (
                        "reusing the model on disk if there is one"
                        if reuse
                        else "PatchCore on the normal training images"
                    )
                    + (", then the test split" if infer else ""),
                    markup=False,
                    highlight=False,
                    soft_wrap=True,
                )
                outcomes.append(
                    pipeline.train_and_score(
                        name,
                        visa_dir=settings.visa_dir,
                        models_dir=models_root,
                        runs_dir=runs_root,
                        reuse=reuse,
                        infer=infer,
                        bench=bench,
                        seed=seed,
                        backbone=backbone,
                    )
                )
            if results_path is not None:
                results.write_results(
                    results_path,
                    results.collect(
                        chosen,
                        models_dir=models_root,
                        runs_dir=runs_root,
                        written_by=["spec-to-inspector", *sys.argv[1:]],
                    ),
                )
    except RuntimeError as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error

    out.print(console.outcome_table(outcomes))
    for line in console.outcome_lines(outcomes, models_root, runs_root):
        out.print(line, markup=False, highlight=False, soft_wrap=True)
    if results_path is not None:
        out.print(f"Figures: {results_path}", markup=False, highlight=False, soft_wrap=True)


def _read_specification(spec: Path) -> Specification:
    """Read a clause table, or say why it cannot be read and exit.

    Args:
        spec: The clause table's path, as `parse` writes it.

    Returns:
        The specification.

    Raises:
        typer.Exit: With code 1, if the file cannot be read or is not a
            valid clause table.
    """
    try:
        return read_clause_table(spec)
    except OSError as error:
        err.print(
            f"cannot read the specification {spec}: {error}",
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        raise typer.Exit(code=1) from error
    except ValueError as error:
        err.print(
            f"{spec} is not a valid clause table: {error}",
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        raise typer.Exit(code=1) from error


@app.command()
def inspect(  # noqa: PLR0915 - one verb: its checks, its two sources and its report
    images: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Board images to score with the category's anomaly model and then judge.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="The part the boards are, such as pcb4."),
    ] = None,
    run: Annotated[
        Path | None,
        typer.Option(
            "--run",
            help="A run directory the anomaly model already wrote, such as "
            "<runs-dir>/pcb4/test, to judge instead of image files.",
        ),
    ] = None,
    spec: Annotated[
        Path,
        typer.Option("--spec", help="The specification's clause table, as `parse` writes it."),
    ] = Path("specs/pcb-spec.clauses.json"),
    url: Annotated[
        str | None,
        typer.Option(
            "--url",
            help="The judge's OpenAI-compatible server, up to and including /v1. "
            "Defaults to the settings' VLM URL.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="The model's name on that server. Defaults to the settings' VLM model.",
        ),
    ] = None,
    batch: Annotated[
        str | None,
        typer.Option(
            "--batch",
            help="The name of the run the image files are scored into, "
            "<runs-dir>/<category>/<batch>/, replaced whole. Defaults to `inspect`.",
        ),
    ] = None,
    image_id: Annotated[
        list[str] | None,
        typer.Option(
            "--image-id", help="Judge only this image of --run. May be repeated; kept in order."
        ),
    ] = None,
    max_regions: Annotated[
        int,
        typer.Option(
            "--max-regions",
            min=1,
            help="The most flagged areas per image to put to the judge, most anomalous first. "
            "An image with more is not accepted on the ones judged.",
        ),
    ] = 3,
    corrections: Annotated[
        bool | None,
        typer.Option(
            "--corrections/--no-corrections",
            help="Show the judge the engineers' corrections from the corrections store. "
            "On by default when the store holds any; --no-corrections judges as if it were empty.",
        ),
    ] = None,
) -> None:
    """Judge board images against the specification's clauses, one decision per image.

    Each flagged area is measured, shown to the VLM with the clause table, and
    decided by rule from the clause it cites: accept, reject or needs review.
    The decision is written as `decision.json` beside the anomaly model's
    result, and one line per image is printed. Give image files, which are
    scored first, or --run for a directory already scored. Corrections
    recorded with `correct` are shown to the judge unless switched off.
    """
    if category is None:
        raise typer.BadParameter("give the part with --category", param_hint="--category")
    if (run is None) == (not images):
        raise typer.BadParameter("give image files or --run, not both and not neither")
    if run is not None and batch is not None:
        raise typer.BadParameter(
            "--batch names the run that image files are scored into; --run already names one",
            param_hint="--batch",
        )
    if run is None and image_id:
        raise typer.BadParameter(
            "--image-id picks images of --run; image files are all judged",
            param_hint="--image-id",
        )

    specification = _read_specification(spec)
    if category not in specification.categories():
        raise typer.BadParameter(
            f"the specification has no clause for part {category}; its parts are "
            f"{', '.join(specification.categories())}",
            param_hint="--category",
        )

    settings = Settings()
    # The judge reads the anomaly model's records, which load PyTorch; Anomalib itself, about
    # ten seconds, is loaded only when image files have to be scored first.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        from spec_to_inspector.corrections import recall as recalling  # noqa: PLC0415
        from spec_to_inspector.corrections.store import CorrectionStore  # noqa: PLC0415
        from spec_to_inspector.judge import console as verdicts  # noqa: PLC0415
        from spec_to_inspector.judge import inspect as judging  # noqa: PLC0415
        from spec_to_inspector.judge.client import ChatClient  # noqa: PLC0415

    try:
        store = CorrectionStore(settings.corrections_path)
        held = store.count()
        shown = held > 0 and corrections is not False
        strategy = recalling.RecallStrategy(settings.corrections_recall)
        if shown:
            how = (
                "the judge is shown the part's latest"
                if strategy is recalling.RecallStrategy.PART
                else "the judge is asked again with those made on its own answer"
            )
            err.print(
                f"Corrections: {held} recorded in {store.path}; {how}",
                markup=False,
                highlight=False,
                soft_wrap=True,
            )
        if run is not None:
            run_directory = run
            index = judging.read_run_index(run_directory)
            if index.category != category:
                raise judging.InspectError(
                    f"{run_directory} is a run of part {index.category}, not of {category}"
                )
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                from spec_to_inspector.anomaly import infer  # noqa: PLC0415
                from spec_to_inspector.anomaly.train import (  # noqa: PLC0415
                    ModelNotTrainedError,
                )
            run_directory = infer.run_dir(settings.runs_dir, category, batch or "inspect")
            try:
                items = [
                    infer.InferenceItem(image_id=path.stem, path=path) for path in images or ()
                ]
                scorer = infer.AnomalyModel.load(settings.models_dir, category)
            except ModelNotTrainedError as error:
                raise judging.InspectError(
                    f"{error}; train it with `spec-to-inspector train --category {category}`"
                ) from error
            err.print(
                f"Scoring {len(items)} image(s) with the {category} anomaly model into "
                f"{run_directory}",
                markup=False,
                highlight=False,
                soft_wrap=True,
            )
            infer.run_inference(scorer, items, run_directory)

        with ChatClient(
            url or settings.vlm_url,
            model or settings.vlm_model,
            timeout_seconds=settings.vlm_timeout_seconds,
        ) as client:
            decisions = judging.judge_run(
                run_directory,
                specification,
                client,
                image_ids=image_id or None,
                max_regions=max_regions,
                on_decision=lambda decision: out.print(
                    verdicts.verdict_line(decision), markup=False, highlight=False, soft_wrap=True
                ),
                **recalling.judge_options(store, strategy, in_prompt=shown),
            )
    except (judging.InspectError, ValueError, RuntimeError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error

    out.print(
        verdicts.summary_line(decisions, run_directory),
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    unasked = verdicts.unreachable(decisions)
    if unasked:
        err.print(
            f"{unasked} of {len(decisions)} images could not be put to the judge at "
            f"{url or settings.vlm_url}: start it with scripts/serve_vlm.sh start",
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        raise typer.Exit(code=1)


@app.command()
def correct(
    run: Annotated[
        Path,
        typer.Option("--run", help="The run directory the image was judged in."),
    ],
    image_id: Annotated[
        str,
        typer.Option("--image-id", help="The image of the run whose decision is overridden."),
    ],
    clause: Annotated[
        str | None,
        typer.Option(
            "--clause",
            help="The clause that does cover the flagged area: a numbered heading of the "
            "board's part, such as 5.5, or one of its rows.",
        ),
    ] = None,
    defect_class: Annotated[
        str | None,
        typer.Option(
            "--defect-class",
            help="The defect class it is. Optional with --clause, whose class is checked "
            "against it; alone, it stands for its clause.",
        ),
    ] = None,
    no_defect: Annotated[
        bool,
        typer.Option("--no-defect", help="The flagged area shows no defect: no clause applies."),
    ] = False,
    region: Annotated[
        int | None,
        typer.Option(
            "--region",
            min=1,
            help="The flagged area overridden, by its index. Defaults to the one the "
            "decision rests on.",
        ),
    ] = None,
    note: Annotated[
        str,
        typer.Option("--note", help="A line for the judge: what the area shows, and why."),
    ] = "",
    spec: Annotated[
        Path,
        typer.Option("--spec", help="The specification's clause table, as `parse` writes it."),
    ] = Path("specs/pcb-spec.clauses.json"),
) -> None:
    """Record an engineer's override of the judge on one flagged area of a judged image.

    The judge's own answer is read from the image's decision; the corrected
    class and clause are checked against the clause table of the board's part.
    The override is kept in the corrections store and shown to the judge on
    later boards, and the image's decision is flagged as overridden.
    """
    if no_defect and (clause is not None or defect_class is not None):
        raise typer.BadParameter(
            "--no-defect says that no clause applies; give it or a clause, not both"
        )
    if not no_defect and clause is None and defect_class is None:
        raise typer.BadParameter("give the clause with --clause, or --no-defect")

    specification = _read_specification(spec)
    settings = Settings()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        from spec_to_inspector.corrections.override import record_override  # noqa: PLC0415
        from spec_to_inspector.corrections.render import render_correction  # noqa: PLC0415
        from spec_to_inspector.corrections.store import CorrectionStore  # noqa: PLC0415
        from spec_to_inspector.judge import inspect as judging  # noqa: PLC0415

    store = CorrectionStore(settings.corrections_path)
    try:
        index = judging.read_run_index(run)
        if image_id not in {entry.image_id for entry in index.entries}:
            raise judging.InspectError(f"the run {run} holds no image {image_id}")
        kept = record_override(
            store,
            run / image_id,
            specification,
            region_index=region,
            clause_id=clause,
            defect_class=defect_class,
            note=note,
        )
    except (ValueError, RuntimeError) as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error

    out.print(
        f"Recorded correction {kept.id} of {kept.image_id}, region {kept.region_index}, "
        f"in {store.path}",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    out.print(render_correction(kept), markup=False, highlight=False, soft_wrap=True)


@app.command()
def bench() -> None:
    """Run the pipeline on the labelled set and write the measured figures."""
    _not_built("bench", "U7")


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="The address to listen on. The default serves this machine alone; the console "
            "has no login, so give another address only on a network you trust.",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int, typer.Option("--port", min=1, max=65535, help="The port to listen on.")
    ] = 8130,
    spec: Annotated[
        Path | None,
        typer.Option(
            "--spec",
            help="A clause table `parse` wrote, to start with; the PDF of the same name "
            "beside it is shown with it. By default the console starts with the last "
            "specification uploaded to it, if any.",
        ),
    ] = None,
    state_dir: Annotated[
        Path | None,
        typer.Option(
            "--state-dir",
            help="Where the console keeps the uploaded specification and its training logs. "
            "Defaults to .console under the settings' runs directory.",
        ),
    ] = None,
) -> None:
    """Serve the local inspection console: Specification, Train, Batch and the reject card.

    The console reads the runs and the models from the settings' directories,
    as `train` and `inspect` leave them, and is server-rendered: open the
    address it prints in a browser.
    """
    settings = Settings()
    # The console reads the judge's records, which load PyTorch; loaded for this verb only.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import uvicorn  # noqa: PLC0415

        from spec_to_inspector.app.server import build_console  # noqa: PLC0415
        from spec_to_inspector.app.sink import InMemorySink  # noqa: PLC0415
        from spec_to_inspector.app.specs import SpecError  # noqa: PLC0415

    try:
        # The corrections store is joined here: pass it in place of the in-memory sink.
        console = build_console(
            settings, state_dir=state_dir, spec=spec, sink=InMemorySink(), host=host
        )
    except SpecError as error:
        err.print(str(error), markup=False, highlight=False, soft_wrap=True)
        raise typer.Exit(code=1) from error
    err.print(
        f"Console: http://{host}:{port}/ (runs {settings.runs_dir}, models {settings.models_dir}). "
        "Ctrl-C stops it.",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    err.print(
        "Overrides recorded on a card are kept in this process's memory until the corrections "
        "store is joined.",
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    uvicorn.run(console, host=host, port=port, log_level="warning")
