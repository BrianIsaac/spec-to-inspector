"""Tests for what `inspect` leaves for people: a reject card per rejected board and a report."""

from pathlib import Path

import pytest

from spec_to_inspector.anomaly.records import ImageResult
from spec_to_inspector.batch.report import CARD_NAME, REPORT_NAME, STYLE_NAME, write_report
from spec_to_inspector.judge.decision import Corrected
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import (
    DECISION_NAME,
    RESULT_NAME,
    load_decision,
    write_decision,
)
from tests.batch.batch_fakes import judged_run
from tests.spec.spec_fakes import specification


@pytest.fixture
def run(tmp_path: Path) -> Path:
    """Judge a run of three boards.

    Returns:
        The run's directory.
    """
    return judged_run(tmp_path / "judged", specification())


def test_a_rejected_board_gets_a_card_and_no_other_board_does(run: Path) -> None:
    """One file per reject, beside the board's decision, and only there."""
    written = write_report(run)

    assert (written.boards, written.accepted, written.rejected, written.referred) == (3, 1, 1, 1)
    assert written.cards == 1
    assert (run / "cut" / CARD_NAME).is_file()
    assert not (run / "calm" / CARD_NAME).exists()
    assert not (run / "odd" / CARD_NAME).exists()


def test_the_card_quotes_the_clause_and_shows_what_the_judge_was_shown(run: Path) -> None:
    """The clause by id, page and words, the crop and overlay, the figures, the model apart."""
    write_report(run)
    decision = load_decision(run / "cut")
    clause = decision.clause
    region = decision.regions[0]
    assert clause is not None
    assert region.measurement is not None
    assert region.crop is not None
    assert region.overlay is not None

    card = (run / "cut" / CARD_NAME).read_text(encoding="utf-8")

    assert f"Clause {clause.id} {clause.title}" in card
    assert f"page {clause.page} of the specification" in card
    assert clause.source_text in card
    assert f"{region.measurement.longest_extent_mm:.2f}" in card
    assert f'src="{region.crop}"' in card
    assert f'src="{region.overlay}"' in card
    assert (run / "cut" / region.crop).is_file()
    assert (run / "cut" / region.overlay).is_file()
    assert "a thin bright line scored across the board face" in card
    assert f'href="../{STYLE_NAME}"' in card
    assert f'href="../{REPORT_NAME}"' in card


def test_the_report_lists_every_board_with_a_link_to_each_card(run: Path) -> None:
    """The counts first, then one row per board in the run's order."""
    write_report(run)
    report = (run / REPORT_NAME).read_text(encoding="utf-8")

    assert (run / STYLE_NAME).is_file()
    assert f'href="cut/{CARD_NAME}"' in report
    assert report.index(">calm<") < report.index(">cut<") < report.index(">odd<")
    assert "3 boards" in report
    assert "1 rejected" in report
    assert "1 accepted" in report
    assert "1 referred" in report
    assert "accura" not in report.lower()


def test_the_sizes_are_read_from_the_disk(run: Path) -> None:
    """What was written, then the whole run directory, each in bytes and as allocated."""
    written = write_report(run)
    report_bytes = (run / REPORT_NAME).stat().st_size + (run / STYLE_NAME).stat().st_size
    card_bytes = (run / "cut" / CARD_NAME).stat().st_size

    assert written.report_bytes == report_bytes
    assert written.cards_bytes == card_bytes
    assert written.run_bytes == sum(
        path.stat().st_size for path in run.rglob("*") if path.is_file()
    )
    assert written.run_disk_bytes >= written.run_bytes - 4096 * 64
    assert written.run_disk_bytes > 0
    assert written.report_disk_bytes >= report_bytes
    assert written.cards_disk_bytes >= card_bytes


def test_writing_it_again_gives_the_same_files(run: Path) -> None:
    """Nothing in them changes from one writing to the next, so two runs can be compared."""
    write_report(run)
    before = (run / REPORT_NAME).read_bytes(), (run / "cut" / CARD_NAME).read_bytes()
    write_report(run)
    assert before == ((run / REPORT_NAME).read_bytes(), (run / "cut" / CARD_NAME).read_bytes())


def test_a_board_no_longer_rejected_loses_its_card(run: Path) -> None:
    """A later judging can change an outcome: a card must not outlive its reject."""
    write_report(run)
    decision = load_decision(run / "cut")
    write_decision(run / "cut", decision.model_copy(update={"outcome": Outcome.ACCEPT}))

    written = write_report(run)

    assert written.cards == 0
    assert not (run / "cut" / CARD_NAME).exists()


def test_a_board_not_yet_judged_is_counted_as_that(run: Path) -> None:
    """`--image-id` judges some boards of a run: the report says what is not judged yet."""
    (run / "odd" / DECISION_NAME).unlink()

    written = write_report(run)

    assert (written.boards, written.not_judged) == (3, 1)
    assert "not yet judged" in (run / REPORT_NAME).read_text(encoding="utf-8")


def test_a_correction_shows_on_the_card(run: Path) -> None:
    """An override or a correction in the prompt is flagged where the reader will see it."""
    decision = load_decision(run / "cut")
    flagged = decision.model_copy(update={"corrected": Corrected(in_prompt=True, overridden=True)})
    write_decision(run / "cut", flagged)

    write_report(run)
    card = (run / "cut" / CARD_NAME).read_text(encoding="utf-8")

    assert "Corrected by an engineer" in card
    assert "Judged with corrections in view" in card


def test_text_from_the_model_is_escaped(run: Path) -> None:
    """A sentence holding markup is shown as text."""
    decision = load_decision(run / "cut")
    region = decision.regions[0]
    assert region.answer is not None
    answer = region.answer.model_copy(update={"reason": "<script>alert('x')</script>"})
    write_decision(
        run / "cut",
        decision.model_copy(update={"regions": (region.model_copy(update={"answer": answer}),)}),
    )

    write_report(run)

    assert "<script>" not in (run / "cut" / CARD_NAME).read_text(encoding="utf-8")


def test_the_frames_keep_the_crops_shape(run: Path) -> None:
    """A crop that is not square is not stretched: its frame takes the size the record names."""
    write_report(run)
    result = ImageResult.model_validate_json(
        (run / "cut" / RESULT_NAME).read_text(encoding="utf-8")
    )
    box = result.regions[0].crop_box
    assert box is not None

    card = (run / "cut" / CARD_NAME).read_text(encoding="utf-8")

    assert f"--w: {box.width}; --h: {box.height}" in card
