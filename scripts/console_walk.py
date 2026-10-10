"""Walk the console along the video's path in a headless browser, and save the screenshots.

    uv run python scripts/console_walk.py --live     judge a fresh batch, then walk it
    uv run python scripts/console_walk.py            walk a batch that is already judged

The walk is the console's end-to-end proof and the source of the deck's
screenshots. It starts the console with the real `serve` verb on a free port
and a fresh state directory, then does what the video shows: upload the
specification's PDF and wait for the clause table; open Train; open the batch;
open a reject card; follow its clause to the page of the specification it is
printed on; record an engineer's override on a board the judge got wrong; have
a second board of the same kind judged again, with that correction now in the
judge's prompt.

With `--live` the batch is made here, by the real `inspect` verb against the
VLM server, which this script starts only once the GPU is free and stops the
moment the second board is judged: the card is shared with other work. Without
it the walk reads a batch judged earlier, puts the second board's recorded
second judgement in place where the live walk judged it, and says so in its
record.

Nothing on a screenshot is edited. The boards opened are chosen by rule from
VisA's own labels (each anomalous board in the batch has exactly one labelled
defect type): the card shown is the first reject on which the judge named the
labelled type; the correction is made on the first board on which it did not,
to the labelled type's clause; the second board is the first other board of
that same labelled type on which the judge made that same mistake. Whatever
the judge then says of it is shot and recorded as it came.

The walk leaves nothing behind it. Its corrections go to a store of its own in
its state directory, never to the settings' store, and the two decisions it
changes (the overridden board's flag, the second board's judgement) are put
back as the judge first left them when it ends, so a batch can be walked again
and again. What a later walk needs of a live one is kept in `.walk` inside the
batch's directory.

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
from contextlib import ExitStack, contextmanager, suppress
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
from spec_to_inspector.judge.inspect import DECISION_NAME, load_decision
from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.schema import Specification, read_clause_table

ROOT: Final = Path(__file__).resolve().parent.parent
VIEWPORT: Final = {"width": 1920, "height": 1080}
PARSE_TIMEOUT_MS: Final = 300_000
JUDGE_TIMEOUT_SECONDS: Final = 1800
NORMAL: Final = "normal"
NOT_REJUDGED: Final = "not judged again"
STORE_VARIABLE: Final = "SPEC_TO_INSPECTOR_CORRECTIONS_DB"
STORE_NAME: Final = "corrections.sqlite3"
KEPT_DIR: Final = ".walk"
"""Inside the batch's directory: the decisions the walk changes, as the judge first left them
(`<image>.judged.json`, put back when the walk ends), the second board's judgement with the
correction in view (`<image>.rejudged.json`), which a walk without `--live` shows, and the
live walk's own times (`live.json`)."""
LIVE_NAME: Final = "live.json"


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
        sibling: The second board of the same kind: what the judge said of it
            before the correction and after, whether the second judgement was
            made by this walk ("live"), read from a live walk's ("recorded")
            or not to be had ("not judged again"), and whether it cites the
            corrected clause. Empty if the batch holds no such board.
        store: Where the walk's corrections went.
        live_walk: The live walk that judged this batch: when it began, its
            wait for the GPU, how long `inspect` took on the batch and on the
            second board. A walk without `--live` reads it from the batch's
            directory; empty if no live walk left it.
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
    sibling: dict[str, str | bool | float] = field(default_factory=dict[str, str | bool | float])
    store: str = "a store of the walk's own in its state directory, deleted when it ends"
    live_walk: dict[str, str | float | None] = field(default_factory=dict[str, str | float | None])
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


def own_store(state_dir: Path) -> dict[str, str]:
    """Give the environment of the walk's own processes: its own corrections store.

    The console and `inspect` read the store's place from the settings, so the
    walk's override goes to a file in its state directory and the settings'
    store, which other work judges with, is never written.

    Args:
        state_dir: The walk's state directory.

    Returns:
        This process's environment with the corrections store moved.
    """
    return os.environ | {STORE_VARIABLE: str(state_dir / STORE_NAME)}


@contextmanager
def console(state_dir: Path) -> Iterator[str]:
    """Serve the console with the real verb for the length of the walk.

    Args:
        state_dir: A fresh state directory, so the console starts with no
            specification and an empty corrections store.

    Yields:
        The console's address.

    Raises:
        WalkError: If the console does not come up.
    """
    port = free_port()
    address = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        verb("serve", "--port", str(port), "--state-dir", str(state_dir)),
        cwd=ROOT,
        env=own_store(state_dir),
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


@contextmanager
def vlm_server(record: Record, *, gpu_free_below: int, gpu_wait_minutes: int) -> Iterator[None]:
    """Keep the VLM server up for the live part of the walk, and stop it when that part ends.

    Args:
        record: The walk's record, which takes the wait for the GPU.
        gpu_free_below: Start the server only below this many MiB in use.
        gpu_wait_minutes: How long to wait for the GPU.

    Yields:
        Nothing; the server answers while the block runs.

    Raises:
        WalkError: If the GPU does not come free, or another server is
            already on the judge's port.
    """
    serve_vlm = str(ROOT / "scripts" / "serve_vlm.sh")
    record.gpu_wait_seconds = round(wait_for_gpu(gpu_free_below, gpu_wait_minutes), 1)
    if (
        subprocess.run([serve_vlm, "status"], check=False, capture_output=True, cwd=ROOT).returncode
        == 0
    ):
        # The card is shared: a server already on the judge's port is someone else's.
        raise WalkError("a VLM server is already up and is not this walk's; it was left alone")
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
        yield
    finally:
        if mine:
            subprocess.run([serve_vlm, "stop"], check=False, cwd=ROOT)


def judge_batch(
    camera: Camera,
    address: str,
    record: Record,
    boards: list[Path],
    table: Path,
    environment: dict[str, str],
) -> None:
    """Judge a fresh batch with the real verb, and shoot it once part of the way through.

    Args:
        camera: The walk's camera, to shoot the batch while it is being judged.
        address: The console's address.
        record: The walk's record.
        boards: The image files to score and judge.
        table: The clause table the console parsed, which `inspect` reads.
        environment: The walk's environment, with its own corrections store.

    Raises:
        WalkError: If `inspect` fails or does not finish.
    """
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
    process = subprocess.Popen(command, cwd=ROOT, env=environment)
    try:
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
        stop(process, signal.SIGTERM)


def keep_judged(run_directory: Path, image_id: str) -> None:
    """Keep a board's decision as the judge first left it, before the walk changes it.

    Args:
        run_directory: The batch's directory.
        image_id: The board.
    """
    kept = run_directory / KEPT_DIR / f"{image_id}.judged.json"
    if not kept.exists():
        kept.parent.mkdir(exist_ok=True)
        shutil.copyfile(run_directory / image_id / DECISION_NAME, kept)


def restore_judged(run_directory: Path) -> None:
    """Put back every decision the walk changed, as the judge first left it.

    Run when a walk ends, and when one begins in case an earlier walk was
    killed before it could.

    Args:
        run_directory: The batch's directory; nothing is done if it is not there.
    """
    for kept in sorted((run_directory / KEPT_DIR).glob("*.judged.json")):
        board = run_directory / kept.name.removesuffix(".judged.json")
        if board.is_dir():
            shutil.copyfile(kept, board / DECISION_NAME)
        kept.unlink()
    with suppress(OSError):
        # Gone only if empty: a live walk's second judgement stays for later walks.
        (run_directory / KEPT_DIR).rmdir()


def rejudge(
    record: Record, run_directory: Path, image_id: str, table: Path, environment: dict[str, str]
) -> str:
    """Have one board of the batch judged again, with the walk's correction in the prompt.

    On a live walk the real `inspect` verb asks the VLM server again and the
    new decision is kept beside the batch. Otherwise the decision a live walk
    kept is put in place.

    Args:
        record: The walk's record.
        run_directory: The batch's directory.
        image_id: The board.
        table: The clause table the console parsed.
        environment: The walk's environment, with its own corrections store.

    Returns:
        "live" if the judge was asked now; "recorded" if a live walk's
        judgement was put in place; "not judged again" if the walk is not
        live and no live walk of this batch kept one.

    Raises:
        WalkError: If `inspect` fails.
    """
    kept = run_directory / KEPT_DIR / f"{image_id}.rejudged.json"
    if record.mode != "live":
        if not kept.is_file():
            return NOT_REJUDGED
        shutil.copyfile(kept, run_directory / image_id / DECISION_NAME)
        return "recorded"
    command = verb(
        "inspect",
        "--category",
        record.category,
        "--run",
        str(run_directory),
        "--image-id",
        image_id,
        "--spec",
        str(table),
    )
    done = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if done.returncode != 0:
        msg = f"inspect of board {image_id} exited with code {done.returncode}"
        raise WalkError(msg)
    shutil.copyfile(run_directory / image_id / DECISION_NAME, kept)
    return "live"


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


@dataclass(frozen=True)
class Picked:
    """The boards the walk opens, chosen by rule.

    Attributes:
        shown: The reject whose card is shot.
        corrected: The board the engineer's override is made on.
        to: The defect type it is corrected to; None for a good board that
            was rejected, which is corrected to "not a defect".
        sibling: A second board of the same labelled type on which the judge
            made the same mistake; None if the batch holds none.
        review: The first board referred for review, if any.
        accepted: The first board accepted, if any.
    """

    shown: Board
    corrected: Board
    to: str | None
    sibling: Board | None
    review: Board | None
    accepted: Board | None


def first_named(board: Board) -> str | None:
    """Give the defect class the judge named for a board's first judged area.

    Args:
        board: The board.

    Returns:
        The class, or None if the judge named none or gave no valid answer.
    """
    if board.decision is None:
        return None
    answers = [region.answer for region in board.decision.regions if region.answer is not None]
    return answers[0].defect_class if answers else None


def pick(  # noqa: PLR0912 - one pass over the batch, one branch per kind of board wanted
    boards: list[Board], sources: dict[str, str], known: dict[tuple[str, str], str]
) -> Picked:
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
        it to (None for a good board); the second board (the first other
        board with the corrected board's label on which the judge named the
        same wrong class, and failing that the first other good board
        rejected, where the corrected board is one); the first board referred
        for review, if any; the first board accepted, if any.

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
    sibling = next(
        (
            board
            for board, label in candidates[1:]
            if label == to and first_named(board) == first_named(corrected)
        ),
        None,
    )
    return Picked(shown, corrected, to, sibling, review, accepted)


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


def live_times(record: Record, run_directory: Path) -> dict[str, str | float | None]:
    """Give the times of the live walk that judged the batch, keeping them if this is that walk.

    Args:
        record: The walk's record, complete but for this.
        run_directory: The batch's directory.

    Returns:
        When the live walk began, its wait for the GPU, and how long
        `inspect` took on the batch and on the second board; empty if this
        walk is not live and no live walk of the batch left its times.
    """
    kept = run_directory / KEPT_DIR / LIVE_NAME
    if record.mode != "live":
        try:
            return json.loads(kept.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    seconds = record.sibling.get("rejudge_seconds")
    times: dict[str, str | float | None] = {
        "started_at": record.started_at,
        "gpu_wait_seconds": record.gpu_wait_seconds,
        "judge_seconds": record.judge_seconds,
        "rejudge_seconds": seconds if isinstance(seconds, float) else None,
    }
    kept.parent.mkdir(exist_ok=True)
    kept.write_text(json.dumps(times, indent=2) + "\n", encoding="utf-8")
    return times


def answer_of(directory: Path) -> tuple[str, str, str]:
    """Read what the judge said of a board's first judged area, and what code decided.

    Args:
        directory: The board's directory in its run.

    Returns:
        The class named, the clause cited (each empty if none) and the
        board's outcome.
    """
    decision = load_decision(directory)
    answers = [region.answer for region in decision.regions if region.answer is not None]
    named = answers[0].defect_class if answers else None
    cited = answers[0].clause_id if answers else None
    return named or "", cited or "", decision.outcome.value


@dataclass(frozen=True)
class Batch:
    """The batch the walk is on, and what it reads the boards by.

    Attributes:
        directory: The batch's directory in the runs directory.
        grid: The batch page's address.
        sources: Each board's source image path, by image id.
        known: VisA's labels by folder and file name.
        table: The clause table the console parsed, which `inspect` reads.
        specification: That table, read.
    """

    directory: Path
    grid: str
    sources: dict[str, str]
    known: dict[tuple[str, str], str]
    table: Path
    specification: Specification

    def label(self, board: Board) -> str:
        """Give VisA's label for a board; empty if the image is not one of the part's."""
        return truth(self.known, self.sources[board.image_id]) or ""


def upload_specification(camera: Camera, address: str, pdf: Path, record: Record) -> None:
    """Shot 3: the specification is dropped in and the clause table fills.

    Args:
        camera: The walk's camera.
        address: The console's address.
        pdf: The specification to upload.
        record: The walk's record, which takes the parse time and the row count.

    Raises:
        WalkError: If the console refuses the upload.
    """
    page = camera.page
    page.goto(address, wait_until="networkidle")
    page.get_by_role("heading", name="No specification is loaded").wait_for()
    camera.window("shot-3-1-no-specification")
    page.set_input_files("#pdf", str(pdf))
    started = time.monotonic()
    page.get_by_role("button", name="Parse specification").click()
    page.locator(".clause-table, .alert").first.wait_for(timeout=PARSE_TIMEOUT_MS)
    if page.locator(".clause-table").count() == 0:
        raise WalkError(page.locator(".alert").inner_text())
    record.parse_seconds = round(time.monotonic() - started, 1)
    record.clauses = page.locator(".clause-row").count()
    camera.window("shot-3-2-clause-table")


def open_reject(camera: Camera, batch: Batch, picked: Picked, record: Record) -> None:
    """Shot 5's reject: the card, its panels, and its clause on the specification's page.

    Args:
        camera: The walk's camera.
        batch: The batch.
        picked: The boards chosen by rule.
        record: The walk's record, which takes the board shown.
    """
    page, shown = camera.page, picked.shown
    page.goto(batch.grid, wait_until="networkidle")
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
        "visa_label": batch.label(shown),
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

    if picked.review is not None:
        page.goto(f"{batch.grid}/{picked.review.image_id}", wait_until="networkidle")
        camera.window("extra-needs-review-card")
    if picked.accepted is not None:
        page.goto(f"{batch.grid}/{picked.accepted.image_id}", wait_until="networkidle")
        camera.window("extra-accepted-card")


def correct(camera: Camera, batch: Batch, picked: Picked, record: Record) -> tuple[str, str]:
    """Shot 6, first half: the engineer disagrees, corrects the judge and says why.

    Args:
        camera: The walk's camera.
        batch: The batch.
        picked: The boards chosen by rule.
        record: The walk's record, which takes the correction made.

    Returns:
        The class and the clause heading corrected to; two empty strings for
        "not a defect".

    Raises:
        WalkError: If the form or the card does not behave as it should.
    """
    page, corrected, to = camera.page, picked.corrected, picked.to
    page.goto(batch.grid, wait_until="networkidle")
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
        heading = heading_for(batch.specification, record.category, to)
        page.select_option("#clause", heading)
        if page.input_value("#defect_class") != to:
            raise WalkError("choosing the clause did not set its defect class in the form")
        note = f"VisA labels this defect '{to}'; the judge named '{said.defect_class}'."
    page.fill("#note", note)
    record.corrected = {
        "image_id": corrected.image_id,
        "visa_label": batch.label(corrected),
        "judged_class": said.defect_class or "",
        "judged_clause": said.clause_id or "",
        "corrected_class": to or "",
        "corrected_clause": heading,
        "note": note,
    }
    camera.window("page-11-1-override-form")
    keep_judged(batch.directory, corrected.image_id)
    page.get_by_role("button", name="Record correction").click()
    page.locator("#corrections").wait_for()
    page.wait_for_load_state("networkidle")
    if page.locator("#verdict .badge-corrected").count() != 1:
        raise WalkError("the card does not show the correction that was recorded")
    camera.window("page-11-2-override-recorded")
    return to or "", heading


def judge_second_board(
    camera: Camera,
    batch: Batch,
    sibling: Board,
    corrected_to: tuple[str, str],
    record: Record,
    environment: dict[str, str],
) -> None:
    """Shot 6, second half: a second board of the same kind is judged with the correction in view.

    The board's card is shot as the judge first left it, the board is judged
    again, and its card is shot as it then stands, whatever the judge says.

    Args:
        camera: The walk's camera.
        batch: The batch.
        sibling: The second board.
        corrected_to: The class and the clause heading the engineer corrected to.
        record: The walk's record, which takes both answers.
        environment: The walk's environment, with its own corrections store.

    Raises:
        WalkError: If judging the board again fails, or it was judged without
            the correction in its prompt.
    """
    page = camera.page
    directory = batch.directory / sibling.image_id
    before = answer_of(directory)
    page.goto(f"{batch.grid}/{sibling.image_id}", wait_until="networkidle")
    camera.window("page-11-3-second-board-before")
    camera.element("page-11-3-second-board-before-model", "#panel-model")
    keep_judged(batch.directory, sibling.image_id)
    started = time.monotonic()
    how = rejudge(record, batch.directory, sibling.image_id, batch.table, environment)
    seconds = round(time.monotonic() - started, 1)
    if how == NOT_REJUDGED:
        record.sibling = {
            "image_id": sibling.image_id,
            "visa_label": batch.label(sibling),
            "before_class": before[0],
            "before_clause": before[1],
            "before_outcome": before[2],
            "rejudged": how,
        }
        print(
            f"board {sibling.image_id} was not judged again: no live walk of this batch kept "
            "its second judgement; walk once with --live for the after",
            flush=True,
        )
        return
    if not load_decision(directory).corrected.in_prompt:
        raise WalkError("the second board was judged without the correction in its prompt")
    after = answer_of(directory)
    record.sibling = {
        "image_id": sibling.image_id,
        "visa_label": batch.label(sibling),
        "before_class": before[0],
        "before_clause": before[1],
        "before_outcome": before[2],
        "after_class": after[0],
        "after_clause": after[1],
        "after_outcome": after[2],
        "cites_corrected": after[:2] == corrected_to,
        "rejudged": how,
    }
    if how == "live":
        record.sibling["rejudge_seconds"] = seconds
    page.goto(f"{batch.grid}/{sibling.image_id}", wait_until="networkidle")
    if page.locator("#verdict .badge-corrected").count() != 1:
        raise WalkError("the second board's card does not say it was judged with corrections")
    camera.window("page-11-4-second-board-after")
    camera.element("page-11-4-second-board-after-model", "#panel-model")
    camera.element("page-11-4-second-board-after-shown", "#panel-shown")


def walk(options: argparse.Namespace) -> Record:
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
    run_directory = settings.runs_dir / options.category / options.batch
    restore_judged(run_directory)
    with ExitStack() as stack:
        state = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="console-walk-")))
        environment = own_store(state)
        address = stack.enter_context(console(state))
        playwright = stack.enter_context(sync_playwright())
        stack.callback(restore_judged, run_directory)
        # The VLM server's own stack, closed the moment the live part is over.
        live = stack.enter_context(ExitStack())
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

        upload_specification(camera, address, options.spec_pdf, record)
        table = state / TABLE_NAME
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
            live.enter_context(
                vlm_server(
                    record,
                    gpu_free_below=options.gpu_free_below,
                    gpu_wait_minutes=options.gpu_wait_minutes,
                )
            )
            judge_batch(
                camera,
                address,
                record,
                choose_boards(settings.visa_dir, options.category, options.boards),
                table,
                environment,
            )
        run = open_run(settings.runs_dir, options.category, options.batch)
        boards = run.boards()
        record.boards = len(boards)
        record.counts = {status.value: n for status, n in count_statuses(boards).items()}
        batch = Batch(
            directory=run.directory,
            grid=f"{address}/batch/{options.category}/{options.batch}",
            sources={board.image_id: run.board(board.image_id).result.image for board in boards},
            known=known,
            table=table,
            specification=specification,
        )
        picked = pick(boards, batch.sources, known)
        open_reject(camera, batch, picked, record)

        # Shot 6: the correction, and a second board judged with it in view: deck page 11.
        corrected_to = correct(camera, batch, picked, record)
        if picked.sibling is not None:
            judge_second_board(camera, batch, picked.sibling, corrected_to, record, environment)
        live.close()

        page.goto(batch.grid, wait_until="networkidle")
        if page.locator(".tile-corrected").count() != 1:
            raise WalkError("the grid does not mark the corrected board")
        camera.window("page-11-5-batch-corrected")
        browser.close()
        record.live_walk = live_times(record, run.directory)
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
