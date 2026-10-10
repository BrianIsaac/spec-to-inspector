"""Route tests for the console: every page, the filter, the form, and what goes wrong.

The console is built over the fake world of `tests.app.console_fakes`: a run
the real inference writer wrote and the real judge decided. The parser and
the training command are stand-ins; `tests/app/test_web_parse.py` puts a real
PDF through docling.
"""

import html
import json
import shutil
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from spec_to_inspector.anomaly.infer import load_result
from spec_to_inspector.app import runs as runs_module
from spec_to_inspector.app.sink import InMemorySink, Override
from spec_to_inspector.app.specs import SpecStore
from spec_to_inspector.app.training import JobState, TrainJob, TrainRunner
from spec_to_inspector.app.web import ConsoleConfig, create_app
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.decision import Decision, RegionDecision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.spec.pdf import PdfError
from spec_to_inspector.spec.schema import Specification
from tests.app.console_fakes import BATCH, MODEL_SENTENCE, World, write_world
from tests.judge.run_fakes import CATEGORY
from tests.spec.spec_fakes import (
    calibration,
    sized_clause,
    specification,
    unconditional_clause,
    zone,
)

PDF = b"%PDF-1.7\nfake body\n%%EOF\n"
TRACKED_PDF = Path("specs/pcb-spec.pdf")
CARD = f"/batch/{CATEGORY}/{BATCH}"


class Parser:
    """A stand-in for docling: answers with a fixed specification, or raises."""

    def __init__(self, result: Specification | Exception) -> None:
        """Set the answer.

        Args:
            result: The specification to return, or the error to raise.
        """
        self.result = result

    def __call__(self, path: Path) -> Specification:
        """Answer as set.

        Args:
            path: The uploaded PDF.

        Returns:
            The fixed specification.
        """
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Console:
    """One console over the fake world, with its client and the things behind it."""

    def __init__(self, world: World, state_dir: Path, *, spec: Path | None) -> None:
        """Build the console.

        Args:
            world: The fake world.
            state_dir: A fresh state directory.
            spec: The clause table to start with, or None to start with none.
        """
        self.parser = Parser(specification())
        self.specs = SpecStore(state_dir, parser=self.parser, initial=spec)
        self.sink = InMemorySink()
        self.script = "import sys; print('pcb9: thresholds chosen', file=sys.stderr)"
        self.trainer = TrainRunner(
            state_dir, command_for=lambda _: [sys.executable, "-c", self.script]
        )
        self.app = create_app(
            ConsoleConfig(
                runs_dir=world.runs_dir,
                models_dir=world.models_dir,
                data_dir=world.root / "data",
                state_dir=state_dir,
            ),
            specs=self.specs,
            sink=self.sink,
            trainer=self.trainer,
        )
        self.client = TestClient(self.app, follow_redirects=False)


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The fake world, written once for the module, with the tracked PDF beside its clause table.

    Returns:
        Where its files are.
    """
    made = write_world(tmp_path_factory.mktemp("web"))
    shutil.copyfile(TRACKED_PDF, made.spec_path.with_name("spec.pdf"))
    return made


@pytest.fixture
def console(world: World, tmp_path: Path) -> Iterator[Console]:
    """A console with the fake specification in force.

    Yields:
        The console.
    """
    made = Console(world, tmp_path / "state", spec=world.spec_path)
    yield made
    made.trainer.stop()


@pytest.fixture
def bare(world: World, tmp_path: Path) -> Console:
    """A console with no specification loaded.

    Returns:
        The console.
    """
    return Console(world, tmp_path / "state", spec=None)


def _other_part() -> Specification:
    """A specification whose only part is `pcb1`, so the fake run's part is not in it."""
    return specification(
        calibrations=(calibration(category="pcb1"),),
        zones=(
            zone("A", 1, category="pcb1"),
            zone("B", 2, category="pcb1", x0=0.0, y0=0.0, x1=1.0, y1=1.0),
        ),
        clauses=(
            sized_clause("4.1.1", "A", category="pcb1"),
            sized_clause("4.1.2", "B", category="pcb1", limit=1.0, limit_text="1.0 mm max"),
            unconditional_clause("4.2", category="pcb1"),
        ),
    )


# The front door and the shell every page shares.


def test_the_front_door_opens_on_the_specification(console: Console) -> None:
    """The console's first page is where the work starts."""
    response = console.client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/specification"


@pytest.mark.parametrize("path", ["/specification", "/train", CARD, f"{CARD}/scratch"])
def test_every_page_carries_the_navigation_and_the_stylesheet(console: Console, path: str) -> None:
    """Each of the four pages is whole HTML with the three destinations and one stylesheet."""
    response = console.client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for link in ('href="/specification"', 'href="/train"', 'href="/batch"'):
        assert link in response.text
    assert 'href="/static/console.css"' in response.text
    assert console.client.get("/static/console.css").status_code == 200


def test_a_page_that_does_not_exist_is_said_in_the_console_own_page(console: Console) -> None:
    """A wrong address gets the console's page with its navigation, not a bare error."""
    response = console.client.get("/nowhere")

    assert response.status_code == 404
    assert 'href="/batch"' in response.text


# Specification.


def test_with_no_specification_the_page_asks_for_the_pdf(bare: Console) -> None:
    """An empty console says so and offers the upload."""
    response = bare.client.get("/specification")

    assert response.status_code == 200
    assert "No specification is loaded" in response.text
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="pdf"' in response.text


def test_the_clause_table_lists_every_clause_with_its_limit_and_page(console: Console) -> None:
    """Each clause is a row: id, title, part, class, zone, limit as printed, page."""
    text = console.client.get("/specification").text

    assert "Fake workmanship specification" in text
    assert "Written for a test." in text
    for clause in specification().clauses:
        assert f'id="clause-{clause.id}"' in text
        assert clause.limit_text in text
    assert "3 clauses" in text
    assert "2 zones" in text


def test_a_clause_opens_on_its_source_text_and_its_page(console: Console) -> None:
    """Choosing a clause marks its row, quotes its text and shows the page it is printed on."""
    text = console.client.get("/specification", params={"clause": "4.1.2"}).text

    assert 'id="clause-4.1.2" class="clause-row is-selected"' in text
    assert "A scratch longer than the limit of its zone is rejected." in text
    assert 'src="/specification/pages/3.png"' in text
    assert "Page 3 of 3" in text


def test_a_clause_the_specification_does_not_have_is_not_found(console: Console) -> None:
    """A clause id that is not in the table is a 404 in words."""
    response = console.client.get("/specification", params={"clause": "9.9"})

    assert response.status_code == 404
    assert "has no clause 9.9" in response.text


def test_a_specification_page_is_served_as_a_picture(console: Console) -> None:
    """The PDF beside the clause table is drawn page by page."""
    response = console.client.get("/specification/pages/2.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert console.client.get("/specification/pages/99.png").status_code == 404


def test_without_a_pdf_there_is_no_page_picture(bare: Console) -> None:
    """A console with no specification has no page to draw."""
    assert bare.client.get("/specification/pages/1.png").status_code == 404


def test_an_uploaded_pdf_fills_the_clause_table(bare: Console) -> None:
    """The upload is parsed and the page then shows its clauses and how long the parse took."""
    response = bare.client.post(
        "/specification", files={"pdf": ("customer.pdf", PDF, "application/pdf")}
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/specification"
    text = bare.client.get("/specification").text
    assert "customer.pdf" in text
    assert 'id="clause-4.2"' in text
    assert "parsed in" in text


def test_an_unreadable_pdf_is_refused_and_the_earlier_table_stays(console: Console) -> None:
    """A file that is not a PDF, and a PDF that does not parse, leave what was in force."""
    not_a_pdf = console.client.post(
        "/specification", files={"pdf": ("notes.pdf", b"just some text", "application/pdf")}
    )
    console.parser.result = PdfError("docling could not convert the file: no pages found")
    broken = console.client.post(
        "/specification", files={"pdf": ("broken.pdf", PDF, "application/pdf")}
    )

    assert not_a_pdf.status_code == 422
    assert "notes.pdf is not a PDF" in not_a_pdf.text
    assert broken.status_code == 422
    assert "docling could not convert the file: no pages found" in broken.text
    for response in (not_a_pdf, broken):
        assert 'role="alert"' in response.text
        assert 'id="clause-4.1.1"' in response.text


def test_an_upload_with_no_file_is_refused_in_words(console: Console) -> None:
    """Pressing the button with nothing chosen is answered by the page, not by a bare error."""
    response = console.client.post("/specification", data={})

    assert response.status_code == 422
    assert "no file was chosen" in response.text


# Train.


def _wait_for(console: Console) -> TrainJob:
    """Wait for the console's training to end.

    Returns:
        The job, ended.
    """
    job = console.trainer.latest()
    assert job is not None
    deadline = time.monotonic() + 10
    while job.state is JobState.RUNNING:
        assert time.monotonic() < deadline, "the job did not end"
        time.sleep(0.02)
    return job


def test_the_train_page_shows_the_threshold_and_where_it_came_from(console: Console) -> None:
    """A trained part shows its threshold, how it was chosen, and what the training took."""
    text = console.client.get("/train").text

    assert 'id="part-pcb9"' in text
    assert "29.800" in text
    assert "tuned on the test split" in text
    assert "0.986" in text
    assert 'action="/train"' in text


def test_starting_a_training_runs_the_command_and_the_page_follows_it(console: Console) -> None:
    """Start launches the job; the page then shows it, and its last line when it has ended."""
    response = console.client.post("/train", data={"category": CATEGORY, "replace": "yes"})

    assert response.status_code == 303
    assert response.headers["location"] == "/train"
    job = _wait_for(console)
    assert job.category == CATEGORY
    text = console.client.get("/train").text
    assert "pcb9: thresholds chosen" in text
    assert "Finished" in text
    assert 'http-equiv="refresh"' not in text


def test_a_running_training_is_shown_with_its_elapsed_time_and_refreshes(console: Console) -> None:
    """While the job runs the page says so, shows the time, and reloads itself."""
    console.script = "import time; time.sleep(30)"
    console.client.post("/train", data={"category": CATEGORY, "replace": "yes"})

    text = console.client.get("/train").text
    busy = console.client.post("/train", data={"category": CATEGORY, "replace": "yes"})

    assert "Training pcb9" in text
    assert "Elapsed" in text
    assert 'http-equiv="refresh"' in text
    assert busy.status_code == 409
    assert "still training" in busy.text


def test_a_failed_training_shows_its_last_lines(console: Console) -> None:
    """A job that exits non-zero is shown as failed, with what it wrote."""
    console.script = "import sys; print('CUDA out of memory', file=sys.stderr); sys.exit(1)"
    console.client.post("/train", data={"category": CATEGORY, "replace": "yes"})
    _wait_for(console)

    text = console.client.get("/train").text

    assert "Failed" in text
    assert "CUDA out of memory" in text


def test_a_training_that_was_stopped_is_not_called_a_failure_of_its_own(console: Console) -> None:
    """A job ended by a signal says which, so a stop is not read as a crash."""
    console.script = "import time; time.sleep(30)"
    console.client.post("/train", data={"category": CATEGORY, "replace": "yes"})
    job = console.trainer.latest()
    assert job is not None
    job.stop()

    text = console.client.get("/train").text

    assert "Stopped by signal 15" in text
    assert "exit code" not in text


@pytest.mark.parametrize(
    ("data", "words"),
    [
        ({"category": "pcb7", "replace": "yes"}, "is not a part"),
        ({"category": "../x", "replace": "yes"}, "is not a part"),
        ({"category": CATEGORY}, "replaces the model"),
        ({}, "choose the part"),
    ],
)
def test_a_training_that_should_not_start_does_not(
    console: Console, data: dict[str, str], words: str
) -> None:
    """An unknown part, and a trained part without the say-so to replace it, start nothing."""
    response = console.client.post("/train", data=data)

    assert response.status_code == 422
    assert words in response.text
    assert console.trainer.latest() is None


# Batch.


def test_the_batch_door_opens_on_the_newest_batch(console: Console) -> None:
    """With batches on disk, Batch goes straight to the most recent one."""
    response = console.client.get("/batch")

    assert response.status_code == 307
    assert response.headers["location"] == CARD


def test_with_no_batch_the_page_says_how_to_make_one(world: World, tmp_path: Path) -> None:
    """A console over an empty runs directory explains what fills it."""
    empty = World(
        root=world.root,
        runs_dir=tmp_path / "runs",
        run=world.run,
        models_dir=world.models_dir,
        spec_path=world.spec_path,
        specification=world.specification,
    )
    response = Console(empty, tmp_path / "state", spec=None).client.get("/batch")

    assert response.status_code == 200
    assert "No batch has been scored yet" in response.text
    assert "spec-to-inspector inspect" in response.text


def test_the_grid_shows_every_board_with_its_disposition(console: Console) -> None:
    """All six boards are tiles, each linking to its card, and the counts head the page."""
    text = console.client.get(CARD).text

    for image_id in ("good", "speck", "scratch", "two", "peak", "late"):
        assert f'href="{CARD}/{image_id}"' in text
    assert text.count('class="tile ') == 6
    for chip in ("All 6", "Accept 2", "Reject 2", "Needs review 1", "Not judged 1"):
        assert chip in " ".join(text.split())


@pytest.mark.parametrize(
    ("disposition", "shown"),
    [
        ("accept", ["good", "speck"]),
        ("reject", ["scratch", "two"]),
        ("needs-review", ["peak"]),
        ("not-judged", ["late"]),
    ],
)
def test_the_filter_keeps_only_one_disposition(
    console: Console, disposition: str, shown: list[str]
) -> None:
    """A filter leaves one disposition's boards, and their cards keep the filter."""
    text = console.client.get(CARD, params={"disposition": disposition}).text

    assert text.count('class="tile ') == len(shown)
    for image_id in shown:
        assert f'href="{CARD}/{image_id}?disposition={disposition}"' in text


def test_a_filter_that_is_not_a_disposition_is_refused(console: Console) -> None:
    """An unknown filter value is an error in words, not an empty grid."""
    response = console.client.get(CARD, params={"disposition": "maybe"})

    assert response.status_code == 422
    assert "is not a disposition" in response.text


def test_a_batch_that_is_not_there_is_not_found_in_words(console: Console) -> None:
    """An unknown batch gets the console's page and the reason."""
    response = console.client.get(f"/batch/{CATEGORY}/absent")

    assert response.status_code == 404
    assert "no batch absent of part pcb9" in response.text


def test_a_run_of_another_part_is_not_shown_under_this_one(world: World, tmp_path: Path) -> None:
    """A run filed under a part its index does not name is refused, with both parts named."""
    runs = tmp_path / "runs"
    shutil.copytree(world.run, runs / "pcb1" / BATCH)
    moved = World(
        root=world.root,
        runs_dir=runs,
        run=runs / "pcb1" / BATCH,
        models_dir=world.models_dir,
        spec_path=world.spec_path,
        specification=world.specification,
    )
    console = Console(moved, tmp_path / "state", spec=world.spec_path)

    response = console.client.get(f"/batch/pcb1/{BATCH}")

    assert response.status_code == 404
    assert "is a run of part pcb9, not of pcb1" in response.text
    assert console.client.get("/batch").status_code == 200


# The card.


def test_the_reject_card_quotes_the_clause_and_shows_what_was_measured(
    console: Console, world: World
) -> None:
    """A reject quotes its clause and shows the measurement against the limit.

    The clause comes with its page and its text; code's sentence and the
    model's are each shown as their own.
    """
    decision = load_decision(world.run / "scratch")
    region = decision.regions[0]
    assert region.measurement is not None

    text = html.unescape(console.client.get(f"{CARD}/scratch").text)

    assert '<span class="badge badge-reject">Reject</span>' in text
    assert "Clause 4.1.1" in text
    assert "Scratch" in text
    assert "page 3" in text
    assert "A scratch longer than the limit of its zone is rejected." in text
    assert "0.5 mm max" in text
    assert f"{region.measurement.longest_extent_mm:.2f} mm" in text
    assert decision.reason.split(": ", 1)[1] in text
    assert MODEL_SENTENCE in text
    assert f'src="{CARD}/scratch/regions/1/crop.png"' in text
    assert f'src="{CARD}/scratch/regions/1/heatmap.png"' in text
    assert "<polygon" in text
    assert 'href="/specification?clause=4.1.1#clause-4.1.1"' in text


def test_the_measured_extent_is_drawn_on_the_crop_in_the_crop_own_pixels(
    console: Console, world: World
) -> None:
    """The rectangle's corners are the measurement's, moved by the crop's corner."""
    decision = load_decision(world.run / "scratch")
    measurement = decision.regions[0].measurement
    assert measurement is not None
    board = console.client.get(f"{CARD}/scratch").text
    start = board.index('<polygon class="extent" points="') + len(
        '<polygon class="extent" points="'
    )
    points = [
        tuple(float(number) for number in pair.split(","))
        for pair in board[start : board.index('"', start)].split()
    ]

    box = load_result(world.run / "scratch").regions[0].crop_box
    assert box is not None
    crop_x, crop_y = box.x, box.y

    assert len(points) == 4
    for (x, y), (source_x, source_y) in zip(points, measurement.rectangle_px, strict=True):
        assert x == pytest.approx(source_x - crop_x, abs=0.06)
        assert y == pytest.approx(source_y - crop_y, abs=0.06)


def test_a_needs_review_card_says_why_an_engineer_must_decide(console: Console) -> None:
    """A referral names its cause in words and draws no extent the code did not measure."""
    text = console.client.get(f"{CARD}/peak").text

    assert '<span class="badge badge-needs-review">Needs review</span>' in text
    assert "not measured" in text
    assert "an engineer must decide" in text
    assert "<polygon" not in text
    assert MODEL_SENTENCE in text


def test_an_accepted_board_with_no_flagged_area_says_so(console: Console) -> None:
    """A board the anomaly model passed has no crop, no clause and nothing to correct."""
    text = console.client.get(f"{CARD}/good").text

    assert '<span class="badge badge-accept">Accept</span>' in text
    assert "no area of the board was flagged" in text
    assert "regions/1/crop.png" not in text
    assert 'action="' not in text


def test_a_board_not_yet_judged_shows_what_the_anomaly_model_found(console: Console) -> None:
    """Before the judge has run, the card shows the flagged area and says the judge has not."""
    text = console.client.get(f"{CARD}/late").text

    assert '<span class="badge badge-not-judged">Not judged</span>' in text
    assert f'src="{CARD}/late/regions/1/crop.png"' in text
    assert "has not been judged" in text
    assert 'action="' not in text


def test_a_board_with_two_flagged_areas_shows_either(console: Console) -> None:
    """The card opens on the area the outcome rests on, and the other is one link away."""
    first = console.client.get(f"{CARD}/two").text
    other = console.client.get(f"{CARD}/two", params={"region": 1}).text

    assert f'src="{CARD}/two/regions/2/crop.png"' in first
    assert f'href="{CARD}/two?region=1"' in first
    assert f'src="{CARD}/two/regions/1/crop.png"' in other
    assert console.client.get(f"{CARD}/two", params={"region": 7}).status_code == 404


def test_a_board_the_batch_does_not_hold_is_not_found(console: Console) -> None:
    """An unknown board is a 404 in words."""
    response = console.client.get(f"{CARD}/absent")

    assert response.status_code == 404
    assert "holds no board" in response.text


def test_the_card_steps_to_the_next_board_of_the_same_filter(console: Console) -> None:
    """Opened from a filtered grid, the card's next and previous stay within the filter."""
    text = console.client.get(f"{CARD}/scratch", params={"disposition": "reject"}).text

    assert f'href="{CARD}/two?disposition=reject"' in text
    assert f'href="{CARD}?disposition=reject"' in text
    assert f'href="{CARD}/peak' not in text


# The pictures behind the card.


@pytest.mark.parametrize(
    ("path", "kind", "magic"),
    [
        ("scratch/regions/1/crop.png", "image/png", b"\x89PNG"),
        ("scratch/regions/1/heatmap.png", "image/png", b"\x89PNG"),
        ("scratch/regions/1/overlay.png", "image/png", b"\x89PNG"),
        ("scratch/thumbnail.jpg", "image/jpeg", b"\xff\xd8"),
        ("scratch/board.jpg", "image/jpeg", b"\xff\xd8"),
    ],
)
def test_the_card_pictures_are_served(console: Console, path: str, kind: str, magic: bytes) -> None:
    """The crop and the judge's overlay are the run's own files; the others are drawn."""
    response = console.client.get(f"{CARD}/{path}")

    assert response.status_code == 200
    assert response.headers["content-type"] == kind
    assert response.content.startswith(magic)


@pytest.mark.parametrize(
    "path",
    [
        "scratch/regions/9/crop.png",
        "scratch/regions/9/heatmap.png",
        "late/regions/1/overlay.png",
        "good/regions/1/crop.png",
        "absent/thumbnail.jpg",
    ],
)
def test_a_picture_that_is_not_there_is_not_found(console: Console, path: str) -> None:
    """A region the board does not have, and an overlay the judge never wrote, are 404s."""
    assert console.client.get(f"{CARD}/{path}").status_code == 404


def test_a_board_whose_photograph_is_gone_still_has_a_tile(world: World, tmp_path: Path) -> None:
    """Without the source photograph the thumbnail is the first crop, or nothing at all."""
    runs = tmp_path / "runs"
    shutil.copytree(world.run, runs / CATEGORY / BATCH)
    for result in (runs / CATEGORY / BATCH).glob("*/result.json"):
        result.write_text(
            result.read_text(encoding="utf-8").replace(str(world.root), "/gone"), encoding="utf-8"
        )
    moved = World(
        root=tmp_path,
        runs_dir=runs,
        run=runs / CATEGORY / BATCH,
        models_dir=world.models_dir,
        spec_path=world.spec_path,
        specification=world.specification,
    )
    client = Console(moved, tmp_path / "state", spec=world.spec_path).client

    assert client.get(f"{CARD}/scratch/thumbnail.jpg").status_code == 200
    assert client.get(f"{CARD}/good/thumbnail.jpg").status_code == 404
    assert client.get(f"{CARD}/scratch/board.jpg").status_code == 404
    assert client.get(CARD).status_code == 200
    assert "board.jpg" not in client.get(f"{CARD}/scratch").text


# The override.


def _form(**changes: str) -> dict[str, str]:
    return {
        "region": "1",
        "defect_class": "missing",
        "clause": "4.2",
        "note": "A pad with no part on it, not a scratch.",
    } | changes


def test_an_override_is_recorded_with_what_the_judge_said(console: Console, world: World) -> None:
    """The form's class, clause and note go to the sink with the judged answer beside them."""
    response = console.client.post(f"{CARD}/scratch/override", data=_form())

    assert response.status_code == 303
    assert response.headers["location"] == f"{CARD}/scratch?region=1#corrections"
    (override,) = console.sink.overrides_for(CATEGORY, BATCH, "scratch")
    assert override.model_dump(exclude={"created_at"}) == {
        "category": CATEGORY,
        "run": BATCH,
        "image_id": "scratch",
        "region_index": 1,
        "crop_path": str(world.run / "scratch" / "crops" / "region-001.png"),
        "judged_outcome": Outcome.REJECT,
        "judged_class": "scratch",
        "judged_clause": "4.1",
        "judged_reason": MODEL_SENTENCE,
        "corrected_class": "missing",
        "corrected_clause": "4.2",
        "note": "A pad with no part on it, not a scratch.",
    }
    assert override.created_at.endswith("+00:00")


def test_a_recorded_override_shows_on_the_card_and_in_the_grid(console: Console) -> None:
    """After the correction the card lists it against the clause, and the tile is marked."""
    console.client.post(f"{CARD}/scratch/override", data=_form())

    card = console.client.get(f"{CARD}/scratch").text
    grid = console.client.get(CARD).text

    assert "Corrected by an engineer" in card
    assert "A pad with no part on it, not a scratch." in card
    assert "4.2 Missing component" in card
    assert grid.count("tile-corrected") == 1


def test_an_engineer_may_say_the_area_is_not_a_defect(console: Console) -> None:
    """Leaving class and clause at "not a defect" records a correction that names neither."""
    response = console.client.post(
        f"{CARD}/scratch/override",
        data=_form(defect_class="", clause="", note="Flux residue the wash removes; good board."),
    )

    assert response.status_code == 303
    (override,) = console.sink.overrides_for(CATEGORY, BATCH, "scratch")
    assert override.says_no_defect
    assert "Not a defect" in console.client.get(f"{CARD}/scratch").text


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"clause": "4.1"}, "clause 4.1 is for class"),
        ({"defect_class": "burnt"}, "has no defect class"),
        ({"clause": "9.9"}, "has no clause 9.9"),
        ({"clause": ""}, "together"),
        ({"note": "   "}, "say why"),
        ({"note": "x" * 301}, "300 characters"),
        ({"region": "5"}, "no judged area 5"),
        ({"region": "one"}, "no judged area"),
    ],
)
def test_an_override_that_does_not_hold_together_is_refused(
    console: Console, changes: dict[str, str], words: str
) -> None:
    """A correction that is inconsistent is answered on the card and nothing is recorded.

    A class that is not the clause's, a blank note and an area that was not
    judged are each refused in words.
    """
    response = console.client.post(f"{CARD}/scratch/override", data=_form(**changes))

    assert response.status_code == 422
    assert words in response.text
    assert 'role="alert"' in response.text
    assert console.sink.overrides_for(CATEGORY, BATCH, "scratch") == ()


def test_a_refused_override_keeps_what_the_engineer_typed(console: Console) -> None:
    """The note is not lost to a mistake in another field."""
    response = console.client.post(
        f"{CARD}/scratch/override", data=_form(clause="4.1", note="Keep these words.")
    )

    assert "Keep these words." in response.text


@pytest.mark.parametrize("image_id", ["late", "good"])
def test_a_board_with_nothing_judged_cannot_be_overridden(console: Console, image_id: str) -> None:
    """There is no answer to correct on a board the judge has not answered for."""
    response = console.client.post(f"{CARD}/{image_id}/override", data=_form())

    assert response.status_code == 409
    assert console.sink.overrides_for(CATEGORY, BATCH, image_id) == ()


def test_without_the_specification_the_card_asks_for_it_before_a_correction(bare: Console) -> None:
    """The form's choices are the specification's; with none loaded there is no form."""
    card = bare.client.get(f"{CARD}/scratch")
    posted = bare.client.post(f"{CARD}/scratch/override", data=_form())

    assert card.status_code == 200
    assert "Load the specification" in card.text
    assert 'action="' not in card.text
    assert posted.status_code == 409


def test_a_board_of_a_part_the_specification_does_not_cover_cannot_be_corrected(
    world: World, tmp_path: Path
) -> None:
    """A run of another part than the specification's still opens; its card says what is missing."""
    console = Console(world, tmp_path / "state", spec=None)
    console.parser.result = _other_part()
    console.client.post("/specification", files={"pdf": ("pcb1.pdf", PDF, "application/pdf")})

    card = console.client.get(f"{CARD}/scratch")
    posted = console.client.post(f"{CARD}/scratch/override", data=_form())

    assert card.status_code == 200
    assert "has no clause for part pcb9" in card.text
    assert 'action="' not in card.text
    assert posted.status_code == 409


def test_the_console_writes_to_whatever_sink_it_is_given(world: World, tmp_path: Path) -> None:
    """The corrections store is joined by handing the console another sink."""

    class Store:
        def __init__(self) -> None:
            self.rows: list[Override] = []

        def record(self, override: Override) -> None:
            self.rows.append(override)

        def overrides_for(self, category: str, run: str, image_id: str) -> list[Override]:
            return [row for row in self.rows if row.image_id == image_id]

    store = Store()
    console = Console(world, tmp_path / "state", spec=world.spec_path)
    app = create_app(
        ConsoleConfig(
            runs_dir=world.runs_dir,
            models_dir=world.models_dir,
            data_dir=world.root / "data",
            state_dir=tmp_path / "state",
        ),
        specs=console.specs,
        sink=store,
        trainer=console.trainer,
    )
    client = TestClient(app, follow_redirects=False)

    client.post(f"{CARD}/scratch/override", data=_form())

    assert [row.corrected_clause for row in store.rows] == ["4.2"]
    assert "Corrected by an engineer" in client.get(f"{CARD}/scratch").text


# The corrections loop's flag, drawn when the decision carries it.


class _Flag(BaseModel):
    in_prompt: bool = False
    overridden: bool = False


class _RegionWithCorrections(RegionDecision):
    corrections: tuple[str, ...] = ()
    first_answer: JudgeAnswer | None = None


class _DecisionWithFlag(Decision):
    corrected: _Flag = _Flag()
    regions: tuple[_RegionWithCorrections, ...] = ()  # pyright: ignore[reportIncompatibleVariableOverride]


def test_the_card_draws_the_corrections_flag_when_the_decision_carries_it(
    world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A decision the corrections loop wrote shows what the judge was shown, and its first answer.

    The loop adds `corrected` to the decision and `corrections` and
    `first_answer` to a region; this branch's `Decision` has none of them, so
    the test reads the file with a model that does, as the merged code will.
    """
    runs = tmp_path / "runs"
    shutil.copytree(world.run, runs / CATEGORY / BATCH)
    path = runs / CATEGORY / BATCH / "scratch" / "decision.json"
    written = json.loads(path.read_text(encoding="utf-8"))
    written["corrected"] = {"in_prompt": True, "overridden": True}
    written["regions"][0]["corrections"] = [
        "On a pcb9 board the judge said 'missing'; it is 'scratch'."
    ]
    written["regions"][0]["first_answer"] = {
        "reason": "a pad with nothing on it",
        "defect_class": "missing",
        "clause_id": "4.2",
    }
    path.write_text(json.dumps(written), encoding="utf-8")
    monkeypatch.setattr(runs_module, "Decision", _DecisionWithFlag)
    moved = World(
        root=world.root,
        runs_dir=runs,
        run=runs / CATEGORY / BATCH,
        models_dir=world.models_dir,
        spec_path=world.spec_path,
        specification=world.specification,
    )
    client = Console(moved, tmp_path / "state", spec=world.spec_path).client

    card = html.unescape(client.get(f"{CARD}/scratch").text)
    plain = client.get(f"{CARD}/two").text
    grid = client.get(CARD).text

    assert "Judged with corrections in view" in card
    assert "Corrected by an engineer" in card
    assert "On a pcb9 board the judge said 'missing'; it is 'scratch'." in card
    assert "Before it was shown corrections" in card
    assert "Judged with corrections in view" not in plain
    assert "Corrected by an engineer" not in plain
    assert grid.count("tile-corrected") == 1
