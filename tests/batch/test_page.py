"""Tests for the batch's page and `two-runs.md`: every figure from a file, none typed."""

import json
import shutil
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from spec_to_inspector.batch.page import read_run, render_page, render_two_runs, write_pages
from spec_to_inspector.batch.record import read_batch_record
from spec_to_inspector.cli import app
from tests.batch.conftest import PCB1_REPLIES, PCB4_REPLIES
from tests.bench.conftest import WARM_UP
from tests.judge.fake_vlm import FakeVlm

BATCH = Path("results/stage2/batch")
runner = CliRunner()
DIGESTS = """2026-11-07T11:04:15Z
$ sha256sum ~/week2/run-2/models/patchcore/*/model.ckpt
{pcb1}  /home/devcloud/week2/run-2/models/patchcore/pcb1/model.ckpt
{pcb4}  /home/devcloud/week2/run-2/models/patchcore/pcb4/model.ckpt
$ cmp -l run-1/models/patchcore/pcb1/model.ckpt run-2/models/patchcore/pcb1/model.ckpt | wc -l
36
$ cmp -l run-1/models/patchcore/pcb1/model.ckpt run-2/models/patchcore/pcb1/model.ckpt (offset)
    59761  61  62
$ cmp -l run-1/models/patchcore/pcb4/model.ckpt run-2/models/patchcore/pcb4/model.ckpt | wc -l
35
"""


def _one_run(name: str) -> None:
    """Run both parts and write what the wrapper writes.

    Args:
        name: The run's name.
    """
    raw = BATCH / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for part, replies in (("pcb1", PCB1_REPLIES), ("pcb4", PCB4_REPLIES)):
        with FakeVlm([WARM_UP, *replies]) as server:
            result = runner.invoke(
                app,
                [
                    "inspect",
                    "-c",
                    part,
                    "--spec",
                    "specs/pcb-spec.pdf",
                    "--test-split",
                    "--batch",
                    "batch",
                    "--record",
                    (BATCH / f"{part}.json").as_posix(),
                ],
                env={"SPEC_TO_INSPECTOR_VLM_URL": server.url},
            )
        assert result.exit_code == 0, result.output
        for suffix, value in (
            ("start", "2026-11-07T12:00:00Z"),
            ("end", "2026-11-07T12:05:07Z"),
            ("exit", "0"),
            ("pid", "100"),
        ):
            (raw / f"{name}.{part}.{suffix}").write_text(value + "\n", encoding="utf-8")
    for suffix, value in (
        ("start", "2026-11-07T12:00:00Z"),
        ("end", "2026-11-07T12:10:15Z"),
        ("exit", "0"),
        ("pid", "99"),
    ):
        (raw / f"{name}.{suffix}").write_text(value + "\n", encoding="utf-8")
    (raw / f"{name}.cards.csv").write_text(
        "utc,card_0_mib,card_1_mib\n2026-11-07T12:00:00Z,42,29786\n2026-11-07T12:00:05Z,2594,\n",
        encoding="utf-8",
    )


@pytest.fixture
def batch(machine: Path) -> Path:
    """Make two runs' files, as the batch's directory holds them.

    Returns:
        The batch's directory.
    """
    _one_run("run-1")
    for part in ("pcb1", "pcb4"):
        shutil.copy(BATCH / f"{part}.json", BATCH / f"first-run.{part}.json")
    _one_run("run-2")
    named = json.loads(Path("results/stage2/checkpoints.json").read_text(encoding="utf-8"))
    (BATCH / "raw" / "digests-week2.txt").write_text(
        DIGESTS.format(pcb1="a" * 64, pcb4="b" * 64), encoding="utf-8"
    )
    assert set(cast("dict[str, object]", named["named"])) == {"pcb1", "pcb4"}
    return machine / BATCH


def test_the_page_holds_the_figures_of_the_files(batch: Path) -> None:
    """The counts, the wrapper's times, the figures, each as the files have them."""
    page, two = write_pages(batch)
    text = page.read_text(encoding="utf-8")

    record = read_batch_record(batch / "pcb4.json")
    assert text.startswith("# Stage II: the whole batch, end to end")
    assert "It gives no accuracy figure" in text
    assert f"`{'a' * 64}`" in text
    assert "| 36 |" in text
    assert (
        "| run-2, pcb4 | 2026-11-07T12:00:00Z | 2026-11-07T12:05:07Z | 5 min 7 s | 100 | 0 |"
        in text
    )
    assert "10 min 15 s" in text
    assert f"| run-2 | pcb4 | {record.counts.boards} | {record.counts.accepted} |" in text
    assert "| run-2 | both | 7 |" in text
    assert f"{record.times.parse_seconds:.2f} s" in text
    assert "A flagged image, end to end" in text
    assert f"| {record.inspector.minutes_all_parts:.2f} |" in text
    assert "| run-1 | the whole run, the wrapper's |  | 2594 | 29786 | 2 |" in text
    for file in record.protocol:
        assert file.sha256 in text
    assert "accuracy figure" in text
    assert two.is_file()


def test_two_runs_says_which_fields_differ_and_lists_the_values(batch: Path) -> None:
    """Every value that differs, with the times among them; a field that does not is left out."""
    first = read_run(batch, "run-1", "first-run.")
    second = read_run(batch, "run-2", "")
    text = render_two_runs(first, second)

    assert "## The boards" in text
    assert "| pcb4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |" in text
    before = first.records["pcb4"].times.judge_stage_seconds
    after = second.records["pcb4"].times.judge_stage_seconds
    assert before != after
    assert f"| `times.judge_stage_seconds` | {before} | {after} |" in text
    assert "`part`" not in text
    assert "`times.flagged_images`" not in text


def test_a_board_is_named_by_its_id_and_a_changed_answer_shows(batch: Path) -> None:
    """A different sentence on a board is counted, and its value listed under its id."""
    path = batch / "pcb4.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    changed = next(line for line in raw["observations"] if line["sentence"])
    changed["sentence"] = "another sentence altogether"
    path.write_text(json.dumps(raw), encoding="utf-8")

    text = render_two_runs(read_run(batch, "run-1", "first-run."), read_run(batch, "run-2", ""))

    assert "| pcb4 | 5 | 0 | 0 | 0 | 0 | 0 | 1 |" in text
    assert f"`observations[{changed['image_id']}].sentence`" in text
    assert "another sentence altogether" in text


def test_each_run_is_set_against_the_finals_second_board_by_board(batch: Path) -> None:
    """How many boards differ, by each field that is not a time; no citation against a label."""
    second = read_batch_record(batch / "pcb4.json")
    first = read_batch_record(batch / "pcb1.json")
    lines = [
        json.loads(line.model_dump_json()) for line in [*first.observations, *second.observations]
    ]
    lines[0]["sentence"] = "the final said something else"
    (batch.parent / "final").mkdir(parents=True)
    (batch.parent / "final" / "bench.json").write_text(
        json.dumps({"observations": lines}), encoding="utf-8"
    )

    page = render_page(
        batch, [read_run(batch, "run-1", "first-run."), read_run(batch, "run-2", "")]
    )

    assert "## Against the final's second run, board by board" in page
    assert "| run-2 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |" in page


def test_without_the_finals_record_that_section_is_left_out(batch: Path) -> None:
    """A batch run elsewhere has no final to be set against."""
    page = render_page(
        batch, [read_run(batch, "run-1", "first-run."), read_run(batch, "run-2", "")]
    )

    assert "Against the final's" not in page


def test_the_page_renders_with_only_the_files_it_names(batch: Path) -> None:
    """The bench's directories are not read, so the page can be made on the laptop."""
    shutil.rmtree(Path("runs"))
    runs = [read_run(batch, "run-1", "first-run."), read_run(batch, "run-2", "")]
    assert "## The runs" in render_page(batch, runs)
