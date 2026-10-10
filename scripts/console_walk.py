"""Walk the console along the video's path in a headless browser, and save the screenshots.

    uv run python scripts/console_walk.py --live     judge a fresh batch, then walk it
    uv run python scripts/console_walk.py            walk a batch that is already judged

The walk is the console's end-to-end proof and the source of the deck's
screenshots. It starts the console with the real `serve` verb on a free port
and a fresh state directory, then does what the video shows: upload the
specification's PDF and wait for the clause table; open Train; open the batch;
open a reject card; follow its clause to the page of the specification it is
printed on; record an engineer's override on a board the judge got wrong.

With `--live` the batch is made here, by the real `inspect` verb against the
VLM server, which this script starts only once the GPU is free and stops the
moment the batch is judged: the card is shared with other work. Without it
the walk reads a batch judged earlier and says so in its record.

Nothing on a screenshot is edited. The board whose card is shown and the board
that is corrected are chosen by rule from VisA's own labels (each anomalous
board in the batch has exactly one labelled defect type): the card shown is the
first reject on which the judge named the labelled type, and the correction is
made on the first board on which it did not, to the labelled type's clause.

Whole-window screenshots are 1920 by 1080 at a device scale of one, the frame
the video shows; shots of one panel are taken at a scale of two, so a deck can
enlarge them. They are written to `docs/screens/` and named by deck page
(`page-NN-...`) or by video shot (`shot-N-...`); `walk.json` beside them
records what was done.
"""

import argparse
import csv
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Final, NoReturn

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from spec_to_inspector.app.runs import Board, Status, count_statuses, open_run
from spec_to_inspector.app.specs import TABLE_NAME
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

ROOT: Final = Path(__file__).resolve().parent.parent
VIEWPORT: Final = {"width": 1920, "height": 1080}
PARSE_TIMEOUT_MS: Final = 300_000
JUDGE_TIMEOUT_SECONDS: Final = 1800
NORMAL: Final = "normal"


class WalkError(RuntimeError):
    """The walk could not go on; the message says where it stopped and why."""


@dataclass
class Record:
    """What a walk did, written beside its screenshots as `walk.json`.

    Attributes:
        mode: "live" if the batch was judged by this walk, "recorded" otherwise.
        started_at: When the walk began, in UTC, ISO 8601.
        category: The part.
        batch: The batch's name.
        specification: The PDF uploaded.
        clauses: Rows in the clause table after the upload.
        parse_seconds: How long the console took from the upload to the clause table.
        boards: Boards in the batch.
        counts: Boards by disposition.
        gpu_wait_seconds: How long a live walk waited for the GPU to be free.
        judge_seconds: How long `inspect` took on a live walk, scoring included.
        shown: The board whose reject card was shot, with why it was chosen.
        corrected: The board that was overridden, and the correction made.
        screens: The screenshots written, in order.
    """

    mode: str
    started_at: str
    category: str
    batch: str
    specification: str
    clauses: int = 0
    parse_seconds: float = 0.0
    boards: int = 0
    counts: dict[str, int] = field(default_factory=dict[str, int])
    gpu_wait_seconds: float | None = None
    judge_seconds: float | None = None
    shown: dict[str, str] = field(default_factory=dict[str, str])
    corrected: dict[str, str] = field(default_factory=dict[str, str])
    screens: list[str] = field(default_factory=list[str])


class Camera:
    """Takes the walk's screenshots: the window as a video frame, an element at twice the scale.

    Attributes:
        page: The page the walk drives, 1920 by 1080 at a device scale of one.
    """

    def __init__(self, page: Page, sharp: Page, out: Path, record: Record) -> None:
        """Bind the camera to its two pages.

        Args:
            page: The page the walk drives.
            sharp: A page of the same size at a device scale of two, for
                element shots that a deck enlarges.
            out: Where screenshots go.
            record: The walk's record, which lists what was shot.
        """
        self.page = page
        self._sharp = sharp
        self._out = out
        self._record = record

    @staticmethod
    def _settle(page: Page) -> None:
        """Wait until the page has loaded every picture it shows, and refuse a broken one.

        Args:
            page: The page about to be shot.

        Raises:
            WalkError: If a picture on the page failed to load.
        """
        page.wait_for_load_state("networkidle")
        page.wait_for_function(
            "Array.from(document.images).filter((i) => i.loading !== 'lazy')"
            ".every((i) => i.complete)"
        )
        broken = page.evaluate(
            "Array.from(document.images).filter((i) => i.complete && i.naturalWidth === 0"
            " && i.getBoundingClientRect().top < innerHeight).map((i) => i.src)"
        )
        if broken:
            msg = f"{page.url} shows a picture that did not load: {', '.join(broken)}"
            raise WalkError(msg)
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.evaluate("window.scrollTo(0, 0)")

    def _saved(self, name: str) -> str:
        path = self._out / f"{name}.png"
        self._record.screens.append(path.name)
        print(f"shot {path.name}", flush=True)
        return str(path)

    def window(self, name: str) -> None:
        """Save the window as it stands: one frame of the video.

        Args:
            name: The file's name without its suffix.
        """
        self._settle(self.page)
        self.page.screenshot(path=self._saved(name))

    def element(self, name: str, selector: str) -> None:
        """Save one element of the page the walk is on, at twice the scale.

        Args:
            name: The file's name without its suffix.
            selector: The element.
        """
        self._sharp.goto(self.page.url, wait_until="networkidle")
        self._settle(self._sharp)
        self._sharp.locator(selector).screenshot(path=self._saved(name))


def arguments() -> argparse.Namespace:
    """Read the command line.

    Returns:
        The walk's options.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "screens")
    parser.add_argument("--category", default="pcb4", help="the part; default pcb4")
    parser.add_argument("--batch", default="walk", help="the batch's name; default walk")
    parser.add_argument(
        "--boards", type=int, default=24, help="boards in a live batch, a third of them good"
    )
    parser.add_argument("--spec-pdf", type=Path, default=ROOT / "specs" / "pcb-spec.pdf")
    parser.add_argument(
        "--live",
        action="store_true",
        help="judge the batch now: wait for the GPU, start the VLM server, run inspect, stop it",
    )
    parser.add_argument(
        "--gpu-free-below",
        type=int,
        default=3000,
        help="start the VLM server only when the GPU has less than this many MiB in use",
    )
    parser.add_argument(
        "--gpu-wait-minutes", type=int, default=40, help="how long to wait for the GPU"
    )
    return parser.parse_args()


def free_port() -> int:
    """Find a loopback port nothing is listening on.

    Returns:
        The port.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def verb(*words: str) -> list[str]:
    """Build a `spec-to-inspector` command run by this interpreter.

    Args:
        *words: The verb and its arguments.

    Returns:
        The command.
    """
    return [sys.executable, "-c", "from spec_to_inspector.cli import app; app()", *words]


def stop(process: subprocess.Popen[bytes], how: signal.Signals) -> None:
    """Stop a process this walk started, and do not return while it is still running.

    Args:
        process: The process.
        how: The signal to ask with; it is killed if it has not gone in a minute.
    """
    if process.poll() is not None:
        return
    process.send_signal(how)
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def console(state_dir: Path) -> Iterator[str]:
    """Serve the console with the real verb for the length of the walk.

    Args:
        state_dir: A fresh state directory, so the console starts with no specification.

    Yields:
        The console's address.

    Raises:
        WalkError: If the console does not come up.
    """
    port = free_port()
    address = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        verb("serve", "--port", str(port), "--state-dir", str(state_dir)), cwd=ROOT
    )
    try:
        deadline = time.monotonic() + 120
        while True:
            if process.poll() is not None:
                msg = f"the console exited with code {process.returncode} before it answered"
                raise WalkError(msg)
            try:
                httpx.get(f"{address}/specification", timeout=2).raise_for_status()
                break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    raise WalkError("the console did not answer within two minutes") from None
                time.sleep(0.3)
        yield address
    finally:
        stop(process, signal.SIGINT)


def gpu_used_mib() -> int:
    """Read how much GPU memory is in use.

    Returns:
        The memory in use on the first GPU, in MiB.
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise WalkError("nvidia-smi is not on the path, so the GPU's memory cannot be read")
    out = subprocess.run(
        [nvidia_smi, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.splitlines()[0])


def wait_for_gpu(limit_mib: int, minutes: int) -> float:
    """Wait until the GPU is free enough for the VLM server, checking once a minute.

    Args:
        limit_mib: The server is started only below this much memory in use.
        minutes: How many minutes to wait at most.

    Returns:
        How long the wait was, in seconds.

    Raises:
        WalkError: If the GPU is still in use after the wait.
    """
    started = time.monotonic()
    for attempt in range(minutes + 1):
        used = gpu_used_mib()
        if used < limit_mib:
            return time.monotonic() - started
        print(f"GPU: {used} MiB in use, waiting ({attempt} of {minutes} min)", flush=True)
        if attempt < minutes:
            time.sleep(60)
    msg = f"the GPU still had {limit_mib} MiB or more in use after {minutes} minutes"
    raise WalkError(msg)


def labels(visa_dir: Path, category: str) -> dict[tuple[str, str], str]:
    """Read VisA's label for every image of a part.

    Args:
        visa_dir: The dataset directory `data fetch` wrote.
        category: The part.

    Returns:
        The label ("normal", one defect type, or several joined by commas)
        by the image's folder and file name, such as ("Anomaly", "000.JPG").
    """
    path = visa_dir / category / "image_anno.csv"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                (Path(row["image"]).parent.name, Path(row["image"]).name): row["label"]
                for row in csv.DictReader(handle)
            }
    except OSError as error:
        msg = f"cannot read {path}: {error}; run `spec-to-inspector data fetch` first"
        raise WalkError(msg) from error


def choose_boards(visa_dir: Path, category: str, count: int) -> list[Path]:
    """Pick the boards of a live batch from the part's VisA test split, by rule.

    Two in three are the first anomalous test images that carry exactly one
    labelled defect type, one in three the first normal test images, in the
    split file's order, laid out two anomalous then one normal.

    Args:
        visa_dir: The dataset directory.
        category: The part.
        count: How many boards.

    Returns:
        The image files.
    """
    known = labels(visa_dir, category)
    anomalous: list[Path] = []
    normal: list[Path] = []
    with (visa_dir / "split_csv" / "1cls.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["object"] != category or row["split"] != "test":
                continue
            image = Path(row["image"])
            label = known.get((image.parent.name, image.name), "")
            if label == NORMAL:
                normal.append(visa_dir / image)
            elif label and "," not in label:
                anomalous.append(visa_dir / image)
    good = count // 3
    bad = count - good
    if len(anomalous) < bad or len(normal) < good:
        msg = f"part {category} has too few test images for a batch of {count}"
        raise WalkError(msg)
    boards: list[Path] = []
    anomalous, normal = anomalous[:bad], normal[:good]
    while anomalous or normal:
        boards.extend(anomalous[:2])
        boards.extend(normal[:1])
        anomalous, normal = anomalous[2:], normal[1:]
    return boards


def judge_live(
    camera: Camera,
    address: str,
    record: Record,
    boards: list[Path],
    table: Path,
    *,
    gpu_free_below: int,
    gpu_wait_minutes: int,
) -> None:
    """Judge a fresh batch with the real verb, the VLM server up only while it runs.

    Args:
        camera: The walk's camera, to shoot the batch while it is being judged.
        address: The console's address.
        record: The walk's record.
        boards: The image files to score and judge.
        table: The clause table the console parsed, which `inspect` reads.
        gpu_free_below: Start the server only below this many MiB in use.
        gpu_wait_minutes: How long to wait for the GPU.

    Raises:
        WalkError: If the GPU does not come free, another server is already
            on the judge's port, or `inspect` fails.
    """
    serve_vlm = str(ROOT / "scripts" / "serve_vlm.sh")
    record.gpu_wait_seconds = round(wait_for_gpu(gpu_free_below, gpu_wait_minutes), 1)
    if (
        subprocess.run([serve_vlm, "status"], check=False, capture_output=True, cwd=ROOT).returncode
        == 0
    ):
        # The card is shared: a server already on the judge's port is someone else's.
        raise WalkError("a VLM server is already up and is not this walk's; it was left alone")
    process: subprocess.Popen[bytes] | None = None
    mine = True
    try:
        try:
            # Inside the try: a start that is interrupted half way must still be stopped.
            subprocess.run([serve_vlm, "start"], check=True, cwd=ROOT)
        except subprocess.CalledProcessError:
            # The script stops what it launched when a start fails (and fails without
            # launching if the port was taken meanwhile), so nothing of this walk's is up.
            mine = False
            raise
        started = time.monotonic()
        command = verb(
            "inspect",
            "--category",
            record.category,
            "--batch",
            record.batch,
            "--spec",
            str(table),
            *(str(board) for board in boards),
        )
        process = subprocess.Popen(command, cwd=ROOT)
        url = f"{address}/batch/{record.category}/{record.batch}"
        shot = False
        while process.poll() is None:
            if time.monotonic() - started > JUDGE_TIMEOUT_SECONDS:
                raise WalkError("inspect did not finish within half an hour")
            time.sleep(1.0)
            if shot or httpx.get(url, timeout=10).status_code != httpx.codes.OK:
                continue
            page = camera.page
            page.goto(url, wait_until="networkidle")
            judged = page.locator(".tile:not(.tile-not-judged)").count()
            # Shoot once, when the judge is visibly part of the way through the batch.
            if judged >= len(boards) // 3 and page.locator(".tile-not-judged").count() > 0:
                camera.window("shot-5-1-batch-being-judged")
                shot = True
        record.judge_seconds = round(time.monotonic() - started, 1)
        if process.returncode != 0:
            msg = f"inspect exited with code {process.returncode}"
            raise WalkError(msg)
    finally:
        if process is not None:
            stop(process, signal.SIGTERM)
        if mine:
            subprocess.run([serve_vlm, "stop"], check=False, cwd=ROOT)


def truth(known: dict[tuple[str, str], str], image: str) -> str | None:
    """Give VisA's label for a board of the batch.

    Args:
        known: VisA's labels by folder and file name.
        image: The source image's path, as the board's result records it.

    Returns:
        The label, or None if the image is not one of the part's.
    """
    path = Path(image)
    return known.get((path.parent.name, path.name))


def pick(  # noqa: PLR0912 - one pass over the batch, one branch per kind of board wanted
    boards: list[Board], sources: dict[str, str], known: dict[tuple[str, str], str]
) -> tuple[Board, Board, str | None, Board | None, Board | None]:
    """Choose, by rule, the boards the walk opens.

    Args:
        boards: The batch's boards, in the run's order.
        sources: Each board's source image path, by image id.
        known: VisA's labels by folder and file name.

    Returns:
        The reject to show (the first on which the judge named the labelled
        type, one compared against a size limit if there is such, and failing
        that the first reject of a board labelled defective); the board
        to correct (the first on which the judge named another type than the
        label, else the first good board rejected) with the type to correct
        it to (None for a good board); the first board referred for review,
        if any; the first board accepted, if any.

    Raises:
        WalkError: If the batch has no reject, or no board the judge got wrong.
    """
    right: list[Board] = []
    sized: list[Board] = []
    wrong: list[tuple[Board, str | None]] = []
    false_alarms: list[tuple[Board, str | None]] = []
    review: Board | None = None
    accepted: Board | None = None
    for board in boards:
        decision = board.decision
        if decision is None:
            continue
        if board.status is Status.NEEDS_REVIEW and review is None:
            review = board
        if board.status is Status.ACCEPT and accepted is None:
            accepted = board
        label = truth(known, sources[board.image_id])
        answers = [region.answer for region in decision.regions if region.answer is not None]
        if not answers or label is None:
            continue
        named = answers[0].defect_class
        if label == NORMAL:
            if board.status is Status.REJECT:
                false_alarms.append((board, None))
        elif "," in label:
            continue
        elif named == label and board.status is Status.REJECT:
            right.append(board)
            rule = decision.regions[0].rule
            if rule is not None and rule.measured is not None:
                sized.append(board)
        elif named != label:
            wrong.append((board, label))
    rejects = [board for board in boards if board.status is Status.REJECT]
    if not rejects:
        raise WalkError("the batch has no rejected board to show a reject card for")
    defective = [
        board for board in rejects if truth(known, sources[board.image_id]) not in {NORMAL, None}
    ]
    shown = (sized or right or defective or rejects)[0]
    candidates = wrong or false_alarms
    if not candidates:
        raise WalkError("the judge named VisA's own type on every board: nothing to correct")
    corrected, to = candidates[0]
    return shown, corrected, to, review, accepted


def heading_for(specification: Specification, category: str, defect_class: str) -> str:
    """Find the clause heading that covers a defect class of a part.

    Args:
        specification: The specification the console parsed.
        category: The part.
        defect_class: The defect class.

    Returns:
        The numbered heading.
    """
    clauses = specification.clauses_for(category, defect_class)
    if not clauses:
        msg = f"the specification has no clause for {defect_class!r} on part {category}"
        raise WalkError(msg)
    return clauses[0].heading_id


def walk(options: argparse.Namespace) -> Record:  # noqa: PLR0915 - the video's path, in order
    """Walk the video's path and save the screenshots.

    Args:
        options: The command line's options.

    Returns:
        The walk's record.
    """
    settings = Settings()
    out: Path = options.out
    out.mkdir(parents=True, exist_ok=True)
    record = Record(
        mode="live" if options.live else "recorded",
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        category=options.category,
        batch=options.batch,
        specification=os.path.relpath(options.spec_pdf, ROOT),
    )
    known = labels(settings.visa_dir, options.category)
    with (
        tempfile.TemporaryDirectory(prefix="console-walk-") as state,
        console(Path(state)) as address,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch(headless=True)
        page, sharp = (
            browser.new_context(
                viewport=VIEWPORT,  # type: ignore[arg-type]
                device_scale_factor=scale,
                locale="en-GB",
            ).new_page()
            for scale in (1, 2)
        )
        camera = Camera(page, sharp, out, record)

        # Shot 3: the specification is dropped in and the clause table fills.
        page.goto(address, wait_until="networkidle")
        page.get_by_role("heading", name="No specification is loaded").wait_for()
        camera.window("shot-3-1-no-specification")
        page.set_input_files("#pdf", str(options.spec_pdf))
        started = time.monotonic()
        page.get_by_role("button", name="Parse specification").click()
        page.locator(".clause-table, .alert").first.wait_for(timeout=PARSE_TIMEOUT_MS)
        if page.locator(".clause-table").count() == 0:
            raise WalkError(page.locator(".alert").inner_text())
        record.parse_seconds = round(time.monotonic() - started, 1)
        record.clauses = page.locator(".clause-row").count()
        camera.window("shot-3-2-clause-table")
        table = Path(state) / TABLE_NAME
        specification = read_clause_table(table)
        if record.clauses != len(specification.clauses):
            msg = f"the page shows {record.clauses} clauses, the table {len(specification.clauses)}"
            raise WalkError(msg)

        # Shot 4: the anomaly model, trained on good boards alone.
        page.get_by_role("link", name="Train", exact=True).click()
        page.locator(f"#part-{options.category}").wait_for()
        camera.window("shot-4-train-recorded-run")

        # Shot 5: a batch runs.
        if options.live:
            judge_live(
                camera,
                address,
                record,
                choose_boards(settings.visa_dir, options.category, options.boards),
                table,
                gpu_free_below=options.gpu_free_below,
                gpu_wait_minutes=options.gpu_wait_minutes,
            )
        run = open_run(settings.runs_dir, options.category, options.batch)
        boards = run.boards()
        record.boards = len(boards)
        record.counts = {status.value: n for status, n in count_statuses(boards).items()}
        sources = {board.image_id: run.board(board.image_id).result.image for board in boards}
        shown, corrected, to, review, accepted = pick(boards, sources, known)

        grid = f"{address}/batch/{options.category}/{options.batch}"
        page.goto(grid, wait_until="networkidle")
        camera.window("shot-5-2-batch")
        page.locator(".chip-reject").click()
        page.wait_for_load_state("networkidle")
        camera.window("shot-5-3-batch-rejects")

        # A reject opens: deck pages 1, 5 and 6.
        page.locator(f'.tile[href*="/{shown.image_id}?"]').click()
        page.locator("#verdict .badge-reject").wait_for()
        page.wait_for_load_state("networkidle")
        decision = shown.decision
        assert decision is not None  # noqa: S101 - a reject has a decision
        record.shown = {
            "image_id": shown.image_id,
            "clause": decision.clause.id if decision.clause else "",
            "visa_label": truth(known, sources[shown.image_id]) or "",
            "reason": decision.reason,
        }
        camera.window("page-06-reject-card")
        camera.element("page-01-reject-clause-line", "#verdict")
        camera.element("page-05-2-finds", "#panel-area")
        camera.element("page-05-3-measures", "#panel-measured")
        camera.element("page-05-4-names", "#panel-model")
        camera.element("page-05-5-cites", "#panel-clause")
        camera.element("page-05-6-corrects", "#panel-override")

        # The clause, on the page of the specification it is printed on: deck page 7.
        page.locator("#panel-clause .page-ref a").click()
        page.locator(".clause-row.is-selected").wait_for()
        page.wait_for_load_state("networkidle")
        camera.window("page-07-specification-clause")
        camera.element("page-05-1-specification", "#panel-clauses")

        if review is not None:
            page.goto(f"{grid}/{review.image_id}", wait_until="networkidle")
            camera.window("extra-needs-review-card")
        if accepted is not None:
            page.goto(f"{grid}/{accepted.image_id}", wait_until="networkidle")
            camera.window("extra-accepted-card")

        # Shot 6: the engineer disagrees, corrects it and says why: deck page 11.
        page.goto(grid, wait_until="networkidle")
        page.locator(f'.tile[href$="/{corrected.image_id}"]').click()
        page.locator("#panel-override form").wait_for()
        judged = corrected.decision
        assert judged is not None  # noqa: S101 - chosen among judged boards
        said = next(region.answer for region in judged.regions if region.answer is not None)
        if to is None:
            page.select_option("#clause", "")
            page.select_option("#defect_class", "")
            note = "VisA labels this board good: the flagged area is not a defect."
            heading = ""
        else:
            heading = heading_for(specification, options.category, to)
            page.select_option("#clause", heading)
            if page.input_value("#defect_class") != to:
                raise WalkError("choosing the clause did not set its defect class in the form")
            note = f"VisA labels this defect '{to}'; the judge named '{said.defect_class}'."
        page.fill("#note", note)
        record.corrected = {
            "image_id": corrected.image_id,
            "judged_class": said.defect_class or "",
            "judged_clause": said.clause_id or "",
            "corrected_class": to or "",
            "corrected_clause": heading,
            "note": note,
        }
        camera.window("page-11-1-override-form")
        page.get_by_role("button", name="Record correction").click()
        page.locator("#corrections").wait_for()
        page.wait_for_load_state("networkidle")
        if page.locator("#verdict .badge-corrected").count() != 1:
            raise WalkError("the card does not show the correction that was recorded")
        camera.window("page-11-2-override-recorded")
        page.goto(grid, wait_until="networkidle")
        if page.locator(".tile-corrected").count() != 1:
            raise WalkError("the grid does not mark the corrected board")
        camera.window("page-11-3-batch-corrected")
        browser.close()
    return record


def _terminated(signum: int, frame: FrameType | None) -> NoReturn:
    """Turn SIGTERM into an exit, so the walk's cleanup runs.

    Args:
        signum: The signal's number.
        frame: The interrupted frame, unused.

    Raises:
        SystemExit: Always, with the shell's code for the signal.
    """
    del frame
    raise SystemExit(128 + signum)


def main() -> int:
    """Run the walk and write its record.

    Returns:
        The process's exit code.
    """
    options = arguments()
    os.chdir(ROOT)
    # A kill must still stop the VLM server and the console, which are stopped in
    # `finally` blocks: turn it into an exit that unwinds them.
    signal.signal(signal.SIGTERM, _terminated)
    try:
        record = walk(options)
    except (WalkError, PlaywrightError, httpx.HTTPError, subprocess.CalledProcessError) as error:
        print(f"console walk: {error}", file=sys.stderr)
        return 1
    path = options.out / "walk.json"
    path.write_text(json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8")
    print(f"{len(record.screens)} screenshots and {path.name} in {options.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
