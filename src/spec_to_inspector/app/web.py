"""The console's pages: Specification, Train, Batch and the reject card.

Server-rendered with Jinja2; no script is needed to read or to use a page.
The console reads what `parse`, `train` and `inspect` leave on disk and
writes two things only: the specification an engineer uploads, into its state
directory, and an engineer's override, to the corrections sink it was given.
"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Final
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware

from spec_to_inspector.app import pictures
from spec_to_inspector.app.card import (
    FormError,
    RegionCard,
    check_changes_answer,
    check_correction,
    check_note,
    choose_region,
    clause_choices,
    first_answer,
    form_defaults,
    judged_region,
    prompt_corrections,
    region_cards,
    region_number,
)
from spec_to_inspector.app.runs import (
    Board,
    BoardDetail,
    Run,
    RunError,
    Status,
    contained,
    count_statuses,
    is_name,
    list_runs,
    open_run,
    source_image,
    unlisted_runs,
)
from spec_to_inspector.app.sink import (
    CorrectionSink,
    InMemorySink,
    Override,
    OverrideRefusedError,
    SinkError,
)
from spec_to_inspector.app.specs import LoadedSpec, SpecError, SpecStore
from spec_to_inspector.app.training import (
    JobState,
    TrainBusyError,
    TrainRunner,
    read_train_record,
    train_command,
    trained_parts,
)
from spec_to_inspector.datasets.visa import PUBLISHED_COUNTS
from spec_to_inspector.judge.decision import Corrected

_PACKAGE: Final = Path(__file__).parent
_THUMBNAIL_WIDTH: Final = 480
_BOARD_WIDTH: Final = 900
_PAGE_WIDTH: Final = 1100
_REFRESH_SECONDS: Final = 2


@dataclass(frozen=True)
class ConsoleConfig:
    """Where the console reads and writes.

    Attributes:
        runs_dir: The runs directory: `<part>/<batch>/` as the anomaly model writes them.
        models_dir: The models directory: `patchcore/<part>/train.json`.
        data_dir: The data directory, where a board's photograph is looked for
            if it is no longer where inference read it.
        state_dir: The console's own directory: the uploaded specification
            and the training logs.
        hosts: The host names the console answers to; a request that reached
            it under another name is refused, which is what stops a page on
            another site from reaching a console bound to this machine by
            pointing its own name at it. Empty to answer to any name.
    """

    runs_dir: Path
    models_dir: Path
    data_dir: Path
    state_dir: Path
    hosts: tuple[str, ...] = ()


class PageError(Exception):
    """A request the console answers with its own page and a status that is not 200.

    Attributes:
        status: The HTTP status.
        message: What to say, fit to show.
    """

    def __init__(self, status: int, message: str) -> None:
        """Set the status and the message.

        Args:
            status: The HTTP status.
            message: What to say.
        """
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Tile:
    """One board in the batch grid.

    Attributes:
        board: The board and its decision.
        line: What the tile says under the board's name.
        corrected: Whether an engineer has overridden the judge on this board,
            by the console's sink or by the decision's own flag.
        url: The board's card.
    """

    board: Board
    line: str
    corrected: bool
    url: str


def _url(path: str, **params: str | int | None) -> str:
    """Build an address with the query parameters that are set.

    Args:
        path: The path.
        **params: Query parameters; a None is left out.

    Returns:
        The address.
    """
    query = urlencode({key: value for key, value in params.items() if value is not None})
    return f"{path}?{query}" if query else path


def _when(stamp: str) -> str:
    """Give an ISO 8601 time as a date and a time of day, in the console's own time zone.

    Args:
        stamp: The time, as the records keep it.

    Returns:
        Such as "11 Oct 2026, 01:18"; the text unchanged if it is not a time.
    """
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    return f"{moment.astimezone():%-d %b %Y, %H:%M}"


def _duration(seconds: float) -> str:
    """Give a length of time in the units a person reads.

    Args:
        seconds: The time in seconds.

    Returns:
        Such as "4.4 s" under a minute, "12 min 06 s" over.
    """
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest:02d} s"


def _gib(count: int) -> str:
    """Give a byte count in gibibytes.

    Args:
        count: The bytes.

    Returns:
        Such as "7.82 GiB".
    """
    return f"{count / 2**30:.2f} GiB"


def _tile_line(board: Board) -> str:
    """Say in a few words what a tile's disposition rests on.

    Args:
        board: The board and its decision.

    Returns:
        The clause applied, the cause of a referral, or what the anomaly model found.
    """
    decision = board.decision
    if decision is None:
        if board.problem is not None:
            return "Decision unreadable"
        found = board.entry.regions
        if not board.entry.predicted_anomalous:
            return "Not flagged"
        return "1 area flagged" if found == 1 else f"{found} areas flagged"
    if decision.clause is not None:
        return f"{decision.clause.id} {decision.clause.title}"
    if decision.review_cause is not None:
        return decision.review_cause.value.capitalize()
    return "No area flagged" if decision.regions_found == 0 else "Flagged area accepted"


class _Pages:
    """The console's request handlers, over one configuration."""

    def __init__(
        self,
        config: ConsoleConfig,
        specs: SpecStore,
        sink: CorrectionSink,
        trainer: TrainRunner,
    ) -> None:
        """Bind the handlers to what they read and write.

        Args:
            config: Where the console reads and writes.
            specs: The specification in force.
            sink: Where overrides go.
            trainer: Starts trainings.
        """
        self.config = config
        self.specs = specs
        self.sink = sink
        self.trainer = trainer
        self.templates = Jinja2Templates(directory=_PACKAGE / "templates")
        # Jinja2 types its filter table loosely.
        self.templates.env.filters.update(  # pyright: ignore[reportUnknownMemberType]
            when=_when, duration=_duration, gib=_gib
        )

    def render(
        self, request: Request, name: str, *, status: int = 200, **context: object
    ) -> HTMLResponse:
        """Render a page inside the console's shell.

        Args:
            request: The request.
            name: The template's file name.
            status: The HTTP status.
            **context: What the template draws from.

        Returns:
            The page.
        """
        return self.templates.TemplateResponse(
            request, name, {"loaded": self.specs.current(), **context}, status_code=status
        )

    def problem(self, request: Request, status: int, message: str) -> HTMLResponse:
        """Render the console's page for a request it cannot serve.

        Args:
            request: The request.
            status: The HTTP status.
            message: What to say.

        Returns:
            The page.
        """
        return self.render(request, "problem.html", status=status, nav="", message=message)

    def _run(self, category: str, run: str) -> Run:
        try:
            return open_run(self.config.runs_dir, category, run)
        except RunError as error:
            raise PageError(404, str(error)) from error

    def _board(self, category: str, run: str, image_id: str) -> tuple[Run, BoardDetail]:
        opened = self._run(category, run)
        try:
            return opened, opened.board(image_id)
        except RunError as error:
            raise PageError(404, str(error)) from error

    @staticmethod
    def _filter(disposition: str | None) -> Status | None:
        if disposition is None or disposition == "":
            return None
        try:
            return Status(disposition)
        except ValueError:
            known = ", ".join(status.value for status in Status)
            msg = f"{disposition!r} is not a disposition; the filter takes {known}"
            raise PageError(422, msg) from None

    # Specification.

    def front(self) -> RedirectResponse:
        """Send the front door to the Specification page.

        Returns:
            The redirect.
        """
        return RedirectResponse("/specification", status_code=307)

    def _specification_page(
        self,
        request: Request,
        *,
        clause: str | None = None,
        page: int | None = None,
        error: str | None = None,
        status: int = 200,
    ) -> HTMLResponse:
        loaded = self.specs.current()
        if loaded is None:
            return self.render(
                request, "specification.html", status=status, nav="specification", error=error
            )
        specification = loaded.specification
        selected = None
        if clause is not None:
            selected = specification.find(clause)
            if selected is None:
                msg = f"the specification in force has no clause {clause}"
                raise PageError(404, msg)
        shown = page if page is not None else (selected.page if selected else 1)
        return self.render(
            request,
            "specification.html",
            status=status,
            nav="specification",
            error=error,
            specification=specification,
            selected=selected,
            shown=min(max(shown, 1), specification.pages),
            headings=len({row.heading_id for row in specification.clauses}),
        )

    def specification(
        self, request: Request, clause: str | None = None, page: int | None = None
    ) -> HTMLResponse:
        """Show the specification in force: its clause table beside its pages.

        Args:
            request: The request.
            clause: A clause to open on its source text and its page.
            page: A page to show instead of the chosen clause's.

        Returns:
            The page.
        """
        return self._specification_page(request, clause=clause, page=page)

    def upload(
        self, request: Request, pdf: Annotated[UploadFile | None, File()] = None
    ) -> Response:
        """Parse an uploaded specification and take it into force.

        Args:
            request: The request.
            pdf: The uploaded PDF.

        Returns:
            A redirect to the Specification page; or the page with the reason
            the upload was refused, what was in force unchanged.
        """
        try:
            self.specs.install(
                (pdf.filename or "") if pdf is not None else "",
                pdf.file.read() if pdf is not None else b"",
            )
        except SpecError as error:
            return self._specification_page(request, error=str(error), status=422)
        return RedirectResponse("/specification", status_code=303)

    def specification_sheet(self, page: int) -> Response:
        """Draw one page of the specification's PDF.

        Args:
            page: The page, from 1.

        Returns:
            The page as a PNG.
        """
        loaded = self.specs.current()
        if loaded is None or loaded.pdf is None:
            raise PageError(404, "the specification in force has no PDF to draw a page from")
        try:
            data = pictures.pdf_page(loaded.pdf, page, width=_PAGE_WIDTH)
        except pictures.PictureError as error:
            raise PageError(404, str(error)) from error
        return Response(data, media_type="image/png")

    # Train.

    def _parts(self, loaded: LoadedSpec | None) -> tuple[list[str], list[str]]:
        """List the parts the Train page shows, and the parts it offers to train.

        Args:
            loaded: The specification in force.

        Returns:
            The parts with a card (trained, or named by the specification),
            and those with every part `train` knows besides.
        """
        named = set(loaded.specification.categories()) if loaded else set[str]()
        shown = sorted(named | set(trained_parts(self.config.models_dir)))
        return shown, sorted(set(shown) | set(PUBLISHED_COUNTS))

    def _train_page(
        self, request: Request, *, error: str | None = None, status: int = 200
    ) -> HTMLResponse:
        shown, offered = self._parts(self.specs.current())
        records = {part: read_train_record(self.config.models_dir, part) for part in shown}
        job = self.trainer.latest()
        return self.render(
            request,
            "train.html",
            status=status,
            nav="train",
            error=error,
            parts=shown,
            offered=offered,
            records=records,
            job=job,
            running=job is not None and job.state is JobState.RUNNING,
            last=read_train_record(self.config.models_dir, job.category) if job else None,
            refresh=_REFRESH_SECONDS,
        )

    def train(self, request: Request) -> HTMLResponse:
        """Show each part's training, its threshold, and the job in hand.

        Args:
            request: The request.

        Returns:
            The page.
        """
        return self._train_page(request)

    def start_training(
        self,
        request: Request,
        category: Annotated[str, Form()] = "",
        replace: Annotated[str, Form()] = "",
    ) -> Response:
        """Start training a part.

        Args:
            request: The request.
            category: The part.
            replace: "yes" when the engineer agrees to replace a model already trained.

        Returns:
            A redirect to the Train page; or the page with the reason nothing
            was started.
        """
        _, offered = self._parts(self.specs.current())
        if not category:
            return self._train_page(request, error="choose the part to train", status=422)
        if not is_name(category) or category not in offered:
            known = ", ".join(offered)
            return self._train_page(
                request,
                error=f"{category!r} is not a part this console can train; the parts are {known}",
                status=422,
            )
        record = read_train_record(self.config.models_dir, category)
        if record is not None and replace != "yes":
            return self._train_page(
                request,
                error=(
                    f"training {category} again replaces the model trained on "
                    f"{_when(record.created_at)} and its test batch, with the decisions in "
                    "it; tick the box to say so"
                ),
                status=422,
            )
        try:
            self.trainer.start(category)
        except TrainBusyError as error:
            return self._train_page(request, error=str(error), status=409)
        return RedirectResponse("/train", status_code=303)

    # Batch.

    def batches(self, request: Request) -> Response:
        """Open the newest batch, or say how a batch is made.

        Args:
            request: The request.

        Returns:
            A redirect to the most recently scored batch; or a page that
            explains what fills the runs directory.
        """
        runs = list_runs(self.config.runs_dir)
        if not runs:
            return self.render(
                request,
                "batch.html",
                nav="batch",
                runs=[],
                runs_dir=self.config.runs_dir,
                unlisted=unlisted_runs(self.config.runs_dir),
            )
        newest = max(runs, key=lambda run: run.created_at)
        return RedirectResponse(f"/batch/{newest.category}/{newest.name}", status_code=307)

    def batch(
        self, request: Request, category: str, run: str, disposition: str | None = None
    ) -> HTMLResponse:
        """Show a batch as a grid of boards, all of them or those of one disposition.

        Args:
            request: The request.
            category: The part.
            run: The batch's name.
            disposition: A status to keep, as `Status` spells it.

        Returns:
            The page.
        """
        opened = self._run(category, run)
        kept = self._filter(disposition)
        boards = opened.boards()
        base = f"/batch/{category}/{run}"
        tiles: list[Tile] = []
        sink_problem: str | None = None
        for board in boards:
            if kept is not None and board.status is not kept:
                continue
            corrected = board.decision is not None and board.decision.corrected.overridden
            if not corrected and sink_problem is None:
                overrides, sink_problem = self._overrides(category, run, board.image_id)
                corrected = bool(overrides)
            tiles.append(
                Tile(
                    board=board,
                    line=_tile_line(board),
                    corrected=corrected,
                    url=_url(f"{base}/{board.image_id}", disposition=kept.value if kept else None),
                )
            )
        return self.render(
            request,
            "batch.html",
            nav="batch",
            run=opened,
            runs=list_runs(self.config.runs_dir),
            unlisted=unlisted_runs(self.config.runs_dir),
            base=base,
            tiles=tiles,
            sink_problem=sink_problem,
            total=len(boards),
            counts=count_statuses(boards),
            kept=kept,
            statuses=list(Status),
        )

    # The card.

    def _overrides(
        self, category: str, run: str, image_id: str
    ) -> tuple[Sequence[Override], str | None]:
        """List a board's overrides, or say why the sink could not be read.

        A sink that cannot be read must not take the judge's decisions off
        the screen, so the pages show the board without its corrections and
        say what is wrong.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.

        Returns:
            The overrides, newest first, and None; or nothing and the reason.
        """
        try:
            return self.sink.overrides_for(category, run, image_id), None
        except SinkError as error:
            return (), str(error)

    def _card_page(
        self,
        request: Request,
        opened: Run,
        detail: BoardDetail,
        *,
        region: int | None,
        kept: Status | None,
        error: str | None = None,
        typed: dict[str, str] | None = None,
        status: int = 200,
    ) -> HTMLResponse:
        """Draw a board's card, as asked for or as the answer to a form that was refused.

        Args:
            request: The request.
            opened: The batch.
            detail: The board.
            region: The flagged area to open on; the deciding one if None.
            kept: The grid's filter the card was opened from.
            error: Why a correction was refused, to show beside the form.
            typed: What the engineer typed into the refused form.
            status: The response's status.

        Returns:
            The page.
        """
        cards = region_cards(detail)
        try:
            chosen = choose_region(cards, region)
        except RunError as error_:
            raise PageError(404, f"{detail.board.image_id}: {error_}") from error_
        loaded = self.specs.current()
        category, run, image_id = opened.category, opened.name, detail.board.image_id
        base = f"/batch/{category}/{run}"
        filtered = kept.value if kept else None

        boards = [board for board in opened.boards() if kept is None or board.status is kept]
        ids = [board.image_id for board in boards]
        at = ids.index(image_id) if image_id in ids else None
        before = ids[at - 1] if at is not None and at > 0 else None
        after = ids[at + 1] if at is not None and at + 1 < len(ids) else None

        overrides, sink_problem = self._overrides(category, run, image_id)
        choices = clause_choices(loaded.specification, category) if loaded else []
        held_clause, held_class = (
            form_defaults(
                loaded.specification, category, chosen.judged.answer if chosen.judged else None
            )
            if loaded is not None and chosen is not None
            else ("", "")
        )
        return self.render(
            request,
            "card.html",
            status=status,
            nav="batch",
            run=opened,
            detail=detail,
            decision=detail.decision,
            result=detail.result,
            board_status=detail.board.status,
            cards=cards,
            chosen=chosen,
            base=base,
            here=f"{base}/{image_id}",
            tabs={
                card.index: _url(f"{base}/{image_id}", region=card.index, disposition=filtered)
                for card in cards
            },
            grid=_url(base, disposition=filtered),
            previous=_url(f"{base}/{before}", disposition=filtered) if before else None,
            following=_url(f"{base}/{after}", disposition=filtered) if after else None,
            position=(at + 1 if at is not None else None, len(ids)),
            kept=kept,
            photo=source_image(detail.result, data_dir=self.config.data_dir) is not None,
            zones=loaded.specification.zones_of(category) if loaded else (),
            choices=choices,
            blocked=self._blocked(detail, chosen, loaded, bool(choices)),
            overrides=overrides,
            sink_problem=sink_problem,
            reaches_judge=self.sink.reaches_judge,
            flag=detail.decision.corrected if detail.decision else Corrected(),
            shown_corrections=prompt_corrections(chosen.judged if chosen else None),
            before=first_answer(chosen.judged if chosen else None),
            titles={choice.heading_id: choice.title for choice in choices},
            error=error,
            held_clause=(typed or {}).get("clause", held_clause),
            held_class=(typed or {}).get("defect_class", held_class),
            held_note=(typed or {}).get("note", ""),
        )

    @staticmethod
    def _blocked(
        detail: BoardDetail, chosen: RegionCard | None, loaded: LoadedSpec | None, choices: bool
    ) -> str | None:
        """Say why the override form is not offered on a card, if it is not.

        Args:
            detail: The board.
            chosen: The area the card is open on.
            loaded: The specification in force.
            choices: Whether the specification has a clause for the board's part.

        Returns:
            The reason in words, or None when the form is offered.
        """
        decision = detail.decision
        part = detail.result.category
        if decision is None:
            return "This board has not been judged yet, so there is no answer to correct."
        if not decision.regions:
            return (
                "The anomaly model flagged no area on this board, so there is no answer to correct."
            )
        if chosen is None or chosen.judged is None:
            return "This area was not put to the judge, so there is no answer to correct."
        if loaded is None:
            return "Load the specification to record a correction: its clauses are the choices."
        if not choices:
            return (
                f"The specification in force has no clause for part {part}, so a correction "
                "cannot cite one."
            )
        return None

    def board(
        self,
        request: Request,
        category: str,
        run: str,
        image_id: str,
        region: int | None = None,
        disposition: str | None = None,
    ) -> HTMLResponse:
        """Show one board's card: the crop, the heatmap, the clause, the reason, the override.

        Args:
            request: The request.
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.
            region: The flagged area to open on; the deciding one by default.
            disposition: The grid's filter the card was opened from, kept for
                the way back and for stepping to the next board.

        Returns:
            The page.
        """
        opened, detail = self._board(category, run, image_id)
        return self._card_page(
            request, opened, detail, region=region, kept=self._filter(disposition)
        )

    def override(
        self,
        request: Request,
        category: str,
        run: str,
        image_id: str,
        region: Annotated[str, Form()] = "",
        defect_class: Annotated[str, Form()] = "",
        clause: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        disposition: Annotated[str, Form()] = "",
    ) -> Response:
        """Record an engineer's correction of what the judge said about a flagged area.

        Args:
            request: The request.
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.
            region: The flagged area corrected.
            defect_class: The class the engineer gives; empty for "not a defect".
            clause: The clause heading the engineer gives; empty with the class.
            note: Why, in the engineer's words.
            disposition: The grid's filter the card was opened from.

        Returns:
            A redirect to the card, at its corrections; or the card with the
            reason the correction was refused and what was typed: 422 for a
            correction that does not hold together or that the sink will not
            keep, 503 where the sink cannot keep anything.
        """
        opened, detail = self._board(category, run, image_id)
        kept = self._filter(disposition)
        loaded = self.specs.current()
        decision = detail.decision
        if decision is None or not decision.regions:
            raise PageError(409, f"board {image_id} has no judged area to correct")
        if loaded is None or not clause_choices(loaded.specification, category):
            raise PageError(
                409,
                f"no specification with a clause for part {category} is in force, so a "
                "correction cannot cite one",
            )
        typed = {"defect_class": defect_class, "clause": clause, "note": note}
        try:
            judged = judged_region(decision, image_id, region)
            corrected_class, corrected_clause = check_correction(
                loaded.specification, category, defect_class=defect_class, clause=clause
            )
            check_changes_answer(
                loaded.specification, category, judged.answer, (corrected_class, corrected_clause)
            )
            reason = check_note(note)
            answer = judged.answer
            self.sink.record(
                Override(
                    category=category,
                    run=run,
                    image_id=image_id,
                    region_index=judged.index,
                    crop_path=None if judged.crop is None else str(detail.directory / judged.crop),
                    judged_outcome=judged.outcome,
                    judged_class=None if answer is None else answer.defect_class,
                    judged_clause=None if answer is None else answer.clause_id,
                    judged_reason=None if answer is None else answer.reason,
                    corrected_class=corrected_class,
                    corrected_clause=corrected_clause,
                    note=reason,
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                )
            )
        except (FormError, OverrideRefusedError, SinkError) as error:
            shown = region_number(region)
            if shown not in {found.index for found in detail.result.regions}:
                shown = None
            return self._card_page(
                request,
                opened,
                detail,
                region=shown,
                kept=kept,
                error=str(error),
                typed=typed,
                status=503 if isinstance(error, SinkError) else 422,
            )
        back = _url(
            f"/batch/{category}/{run}/{image_id}",
            region=judged.index,
            disposition=kept.value if kept else None,
        )
        return RedirectResponse(f"{back}#corrections", status_code=303)

    # The pictures behind the grid and the card.

    def _region(
        self, category: str, run: str, image_id: str, index: int
    ) -> tuple[BoardDetail, RegionCard]:
        _, detail = self._board(category, run, image_id)
        card = next((card for card in region_cards(detail) if card.index == index), None)
        if card is None:
            raise PageError(404, f"board {image_id} has no flagged area {index}")
        return detail, card

    def thumbnail(self, category: str, run: str, image_id: str) -> Response:
        """Draw a board's tile picture: its photograph, or its first crop without one.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.

        Returns:
            The picture as a JPEG.
        """
        _, detail = self._board(category, run, image_id)
        source = source_image(detail.result, data_dir=self.config.data_dir)
        if source is None:
            crops = (contained(detail.directory, r.crop) for r in detail.result.regions)
            source = next((crop for crop in crops if crop is not None), None)
            if source is None:
                raise PageError(404, f"board {image_id} has no photograph and no crop to show")
        try:
            data = pictures.thumbnail(source, width=_THUMBNAIL_WIDTH)
        except pictures.PictureError as error:
            raise PageError(404, str(error)) from error
        return Response(data, media_type="image/jpeg")

    def photograph(self, category: str, run: str, image_id: str) -> Response:
        """Draw a board's photograph at the size the card shows it.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.

        Returns:
            The picture as a JPEG.
        """
        _, detail = self._board(category, run, image_id)
        source = source_image(detail.result, data_dir=self.config.data_dir)
        if source is None:
            raise PageError(404, f"the photograph of board {image_id} is no longer on disk")
        try:
            data = pictures.thumbnail(source, width=_BOARD_WIDTH)
        except pictures.PictureError as error:
            raise PageError(404, str(error)) from error
        return Response(data, media_type="image/jpeg")

    def crop(self, category: str, run: str, image_id: str, index: int) -> Response:
        """Serve a flagged area's crop, the file the anomaly model cut.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.
            index: The area's index.

        Returns:
            The crop as a PNG.
        """
        detail, card = self._region(category, run, image_id, index)
        path = contained(detail.directory, card.found.crop)
        if path is None:
            raise PageError(404, f"area {index} of board {image_id} has no crop on disk")
        return FileResponse(path, media_type="image/png")

    def heatmap(self, category: str, run: str, image_id: str, index: int) -> Response:
        """Draw the anomaly map over a flagged area's crop.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.
            index: The area's index.

        Returns:
            The heatmap as a PNG.
        """
        detail, card = self._region(category, run, image_id, index)
        try:
            data = pictures.heatmap(detail.directory, detail.result, card.found)
        except pictures.PictureError as error:
            raise PageError(404, str(error)) from error
        return Response(data, media_type="image/png")

    def overlay(self, category: str, run: str, image_id: str, index: int) -> Response:
        """Serve the overlay the judge was shown for a flagged area.

        Args:
            category: The part.
            run: The batch's name.
            image_id: The board's name within the batch.
            index: The area's index.

        Returns:
            The overlay as a PNG.
        """
        detail, card = self._region(category, run, image_id, index)
        path = contained(detail.directory, card.judged.overlay if card.judged else None)
        if path is None:
            raise PageError(404, f"the judge left no overlay for area {index} of board {image_id}")
        return FileResponse(path, media_type="image/png")


def _from_another_site(request: Request) -> bool:
    """Say whether a form was posted by a page that is not the console's own.

    The console has no login, so anything that can post to it can start a
    training or record an override. A browser says where a form came from: in
    `Sec-Fetch-Site`, and in `Origin`, which must be the console's own
    address. A request with neither header is not a browser's cross-site
    form and is let through.

    Args:
        request: The request.

    Returns:
        Whether the browser reports another site as the form's source.
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in {"same-origin", "none"}:
        return True
    origin = request.headers.get("origin")
    return origin is not None and urlsplit(origin).netloc != request.headers.get("host")


def _first_problem(errors: Sequence[Any]) -> str:
    """Put a request FastAPI refused into one sentence.

    Args:
        errors: FastAPI's list of what was wrong, each a mapping with `loc` and `msg`.

    Returns:
        Where the first problem is and what it is.
    """
    if not errors:
        return "the address is not one this console understands"
    where = ".".join(str(part) for part in errors[0].get("loc", ()))
    return f"the address is not one this console understands: {where}: {errors[0].get('msg')}"


def create_app(
    config: ConsoleConfig,
    *,
    specs: SpecStore,
    sink: CorrectionSink | None = None,
    trainer: TrainRunner | None = None,
) -> FastAPI:
    """Build the console.

    Args:
        config: Where the console reads and writes.
        specs: The specification in force, and where uploads are parsed.
        sink: Where the override form records; kept in memory by default.
            This is where the corrections store is joined.
        trainer: Starts trainings; by default the `train` verb into the
            configured models and runs directories.

    Returns:
        The application.
    """
    runner = trainer or TrainRunner(
        config.state_dir,
        command_for=lambda category: train_command(
            category, models_dir=config.models_dir, runs_dir=config.runs_dir
        ),
    )
    pages = _Pages(config, specs, sink if sink is not None else InMemorySink(), runner)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        runner.stop()

    app = FastAPI(
        title="Spec to Inspector console",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.config = config
    app.mount("/static", StaticFiles(directory=_PACKAGE / "static"), name="static")

    board = "/batch/{category}/{run}/{image_id}"
    area = board + "/regions/{index}"
    for path, handler, method in (
        ("/", pages.front, "GET"),
        ("/specification", pages.specification, "GET"),
        ("/specification", pages.upload, "POST"),
        ("/specification/pages/{page}.png", pages.specification_sheet, "GET"),
        ("/train", pages.train, "GET"),
        ("/train", pages.start_training, "POST"),
        ("/batch", pages.batches, "GET"),
        ("/batch/{category}/{run}", pages.batch, "GET"),
        (board, pages.board, "GET"),
        (board + "/override", pages.override, "POST"),
        (board + "/thumbnail.jpg", pages.thumbnail, "GET"),
        (board + "/board.jpg", pages.photograph, "GET"),
        (area + "/crop.png", pages.crop, "GET"),
        (area + "/heatmap.png", pages.heatmap, "GET"),
        (area + "/overlay.png", pages.overlay, "GET"),
    ):
        app.add_api_route(path, handler, methods=[method], response_model=None)

    async def page_error(request: Request, error: Exception) -> Response:
        assert isinstance(error, PageError)  # noqa: S101 - registered for this type alone
        return pages.problem(request, error.status, error.message)

    async def http_error(request: Request, error: Exception) -> Response:
        assert isinstance(error, StarletteHTTPException)  # noqa: S101 - as above
        said = "there is no such page in this console" if error.status_code == 404 else None
        return pages.problem(request, error.status_code, said or str(error.detail))

    async def invalid_request(request: Request, error: Exception) -> Response:
        assert isinstance(error, RequestValidationError)  # noqa: S101 - as above
        return pages.problem(request, 422, _first_problem(error.errors()))

    async def unforeseen(request: Request, error: Exception) -> Response:
        # The server logs the traceback; the page names the kind of fault and no more,
        # since its message may hold a path.
        return pages.problem(
            request, 500, f"something went wrong inside the console ({type(error).__name__})"
        )

    async def same_site_forms(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST" and _from_another_site(request):
            return pages.problem(
                request, 403, "the form was sent from another site, so it was not taken"
            )
        return await call_next(request)

    app.add_exception_handler(PageError, page_error)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(Exception, unforeseen)
    app.middleware("http")(same_site_forms)
    if config.hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.hosts))
    return app
