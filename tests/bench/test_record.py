"""Tests for the bench's record: its file, and the comparison of a run with the one before."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from spec_to_inspector.bench.labels import read_labels
from spec_to_inspector.bench.observe import Citation, DigitReason, DigitReasons, Observation
from spec_to_inspector.bench.record import (
    BOARDS_NOT_SCORED_BY_THE_BENCH,
    SCORE_TOLERANCE,
    BenchRecord,
    FileRef,
    boards_on_threshold,
    compare,
    file_ref,
    missing_for_final,
    protocol_files,
    read_record,
    same_making,
    write_record,
)
from spec_to_inspector.bench.run import BenchPlan
from spec_to_inspector.bench.score import score
from spec_to_inspector.judge.disposition import Outcome


def test_a_record_round_trips_through_its_file(record: BenchRecord, tmp_path: Path) -> None:
    """What is written is what is read, and no partial file is left beside it."""
    path = tmp_path / "results" / "stage1" / "bench.json"
    write_record(path, record)

    assert read_record(path) == record
    assert [entry.name for entry in path.parent.iterdir()] == ["bench.json"]
    assert "Wilson" in record.notes["proportions"]


def test_a_file_that_is_not_a_bench_record_is_refused(tmp_path: Path) -> None:
    """Another unit's figures file is not read as a run of the bench."""
    path = tmp_path / "anomaly.json"
    path.write_text('{"schema_version": 1, "unit": "U2"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        read_record(path)


def test_a_file_is_named_by_its_content(tmp_path: Path) -> None:
    """The digest is of the bytes, so an edited protocol is another protocol."""
    path = tmp_path / "PROTOCOL.md"
    path.write_text("before the run\n", encoding="utf-8")
    first = file_ref(path)
    path.write_text("after the run\n", encoding="utf-8")
    assert first.path == path.as_posix()
    assert first.sha256 != file_ref(path).sha256
    assert len(first.sha256) == 64


def test_a_run_compared_with_itself_differs_in_nothing(record: BenchRecord) -> None:
    """Seven images, four of them answered on region 1, all the same."""
    repeat = compare(record, record)

    assert (repeat.images_compared, repeat.areas_compared) == (7, 4)
    assert repeat.previous_measured_at == record.measured_at
    assert (repeat.heading_differs, repeat.class_differs, repeat.sentence_differs) == (0, 0, 0)
    assert (repeat.flag_differs, repeat.score_differs, repeat.outcome_differs) == (0, 0, 0)
    assert repeat.differing_images == []
    assert repeat.figures_equal
    assert repeat.previous_scores is None


def test_an_answer_that_changed_is_counted_and_named_and_both_figures_are_kept(
    record: BenchRecord, plan: BenchPlan
) -> None:
    """One image cites another heading the second time: the earlier figures stay on record."""
    changed = [
        observation.model_copy(
            update={
                "cited_heading": "5.5",
                "cited_class": "damage",
                "sentence": "a cracked component",
                "outcome": Outcome.NEEDS_REVIEW,
            }
        )
        if observation.key == ("pcb4", "bad-000")
        else observation
        for observation in record.observations
    ]
    later = record.model_copy(
        update={
            "observations": changed,
            "scores": score(read_labels(plan.labels), changed),
            "measured_at": "2026-10-11T09:00:00+00:00",
        }
    )
    repeat = compare(record, later)

    assert (repeat.heading_differs, repeat.class_differs, repeat.sentence_differs) == (1, 1, 1)
    assert repeat.outcome_differs == 1
    assert repeat.differing_images == ["pcb4 bad-000"]
    assert not repeat.figures_equal
    assert repeat.previous_scores == record.scores
    assert later.scores.headline.strict.all.count == 1


def test_a_score_within_the_models_own_repeatability_is_the_same_score(
    record: BenchRecord,
) -> None:
    """A difference in the fourth decimal is not a difference; one in the first is."""

    def shifted(by: float) -> BenchRecord:
        moved = [o.model_copy(update={"score": o.score + by}) for o in record.observations]
        return record.model_copy(update={"observations": moved})

    assert compare(record, shifted(2e-4)).score_differs == 0
    assert compare(record, shifted(0.5)).score_differs == 7


def test_runs_of_another_making_are_not_repeats(record: BenchRecord) -> None:
    """Another server setting or another protocol is another experiment, and is named."""
    assert same_making(record, record) == []
    judge = record.judge.model_copy(update={"image_min_tokens": "the model's own minimum"})
    other = record.model_copy(update={"judge": judge, "limit": 5})
    reasons = same_making(record, other)
    assert len(reasons) == 2
    assert reasons[0].startswith("the limit: None against 5")
    assert "the image token minimum" in reasons[1]


REPOSITORY = Path(__file__).parents[2]


def _board(part: str, image_id: str, score: float) -> Observation:
    return Observation(
        part=part,
        image_id=image_id,
        label="bad",
        score=score,
        flagged=True,
        regions_found=1,
        region1_types=None,
        citation=Citation.NOT_ASKED,
        outcome=Outcome.REJECT,
        corrections_in_prompt=False,
        judge_seconds=0.0,
    )


def test_the_records_already_written_are_read_as_they_are() -> None:
    """Stage I's and week 1's hold one protocol and none of the new fields; they stay readable."""
    for name in ("results/stage1/bench.json", "results/stage2/week1/bench/bench.json"):
        old = read_record(REPOSITORY / name)
        assert [file.path for file in old.protocol] == ["eval/PROTOCOL.md"]
        assert (old.schema_version, old.stage, old.not_final) == (1, "I", [])
        assert old.on_threshold is None
        assert old.judge.cold is None
        assert old.runs["pcb1"].checkpoint is None


def test_the_boards_on_the_threshold_are_those_the_machine_measured() -> None:
    """Week 2's XPU-trained scores: within the tolerance on either side, and the next one is not."""
    thresholds = {"pcb1": 31.319488525390625, "pcb4": 30.048744201660156}
    found = boards_on_threshold(
        [
            _board("pcb1", "bad-029", 31.319490432739258),
            _board("pcb1", "bad-033", 31.334394454956055),
            _board("pcb1", "good-0796", 31.261981964111328),
            _board("pcb4", "bad-081", 30.048744201660156),
            _board("pcb4", "bad-058", 30.173749923706055),
        ],
        thresholds,
    )

    assert [(b.part, b.image_id, b.score, b.threshold, b.above) for b in found.boards] == [
        ("pcb1", "bad-029", 31.319490432739258, 31.319488525390625, True),
        ("pcb4", "bad-081", 30.048744201660156, 30.048744201660156, False),
    ]
    assert found.parts == ("pcb1", "pcb4")


def test_the_protocols_files_are_found_beside_it(tmp_path: Path) -> None:
    """Its additions by their name, in order; another protocol's are not its own."""
    protocol = tmp_path / "PROTOCOL.md"
    protocol.touch()
    second = tmp_path / "PROTOCOL-addition-b-2026-12-02.md"
    second.touch()
    first = tmp_path / "PROTOCOL-addition-a-2026-12-01.md"
    first.touch()
    (tmp_path / "PROTOCOL-stage2-addition-c-2026-12-03.md").touch()

    assert protocol_files(protocol) == [protocol, first, second]


def test_an_addition_made_after_a_run_is_another_making(record: BenchRecord) -> None:
    """A new file in force, or a checkpoint that differs, is not a repeat of the run before."""
    added = FileRef(path="eval/PROTOCOL-addition.md", sha256="0" * 64)
    other = record.model_copy(update={"protocol": [*record.protocol, added]})
    assert "the protocol's files" in same_making(record, other)[0]

    run = record.runs["pcb1"].model_copy(update={"checkpoint": added})
    changed = record.model_copy(update={"runs": {**record.runs, "pcb1": run}})
    assert "the checkpoints" in same_making(record, changed)[0]


def test_a_restart_of_the_same_setting_is_the_same_making(stage2_record: BenchRecord) -> None:
    """The third run follows a restart: when the server started is no part of what it is."""
    cold = stage2_record.judge.cold
    assert cold is not None
    moved = cold.model_copy(update={"server_started_at": "2026-12-01T00:00:00Z"})
    judge = stage2_record.judge.model_copy(update={"cold": moved})

    assert same_making(stage2_record, stage2_record.model_copy(update={"judge": judge})) == []


def test_a_run_of_another_reason_pattern_is_another_making(stage2_record: BenchRecord) -> None:
    """The `designators` comparison's two runs compare with each other, never with the final."""
    judge = stage2_record.judge.model_copy(update={"reason_pattern": "another"})
    other = stage2_record.model_copy(update={"judge": judge})
    assert "the reason's pattern" in same_making(stage2_record, other)[0]


def test_a_repeat_keeps_the_earlier_runs_reasons_with_a_digit(stage2_record: BenchRecord) -> None:
    """The protocol asks for the reasons of both runs, and only the second's file is tracked."""
    reason = DigitReason(
        part="pcb4",
        image_id="bad-080",
        area=1,
        reason="a mark on R12",
        valid=True,
        followed_by_a_unit=False,
    )
    earlier = stage2_record.model_copy(
        update={"digit_reasons": DigitReasons(reasons=(reason,), followed_by_a_unit=0)}
    )
    assert compare(earlier, stage2_record).previous_digit_reasons == earlier.digit_reasons


def test_stage_twos_notes_say_what_is_true_on_the_machine(stage2_record: BenchRecord) -> None:
    """The words the code writes from now on: xpu-smi, the server's start, this protocol."""
    notes = stage2_record.notes

    assert "eval/PROTOCOL-stage2.md" in notes["protocol"]
    assert "PROTOCOL-stage2-addition-region-columns-2026-11-07.md" in notes["protocol"]
    assert "eval/PROTOCOL-stage2.md" in notes["not_held_out"]
    assert "xpu-smi" in notes["units"]
    assert "the server's start" in notes["cold"]
    written = json.dumps(notes)
    assert "nvidia-smi" not in written
    assert "eval/PROTOCOL.md" not in written
    assert "every request was sent with cache_prompt false" not in written


def test_stage_ones_notes_still_say_what_is_true_on_the_laptop(record: BenchRecord) -> None:
    """A laptop's run reads `nvidia-smi` and asks cold by the request."""
    assert "nvidia-smi" in record.notes["units"]
    assert "cache_prompt false" in record.notes["cold"]
    assert "eval/PROTOCOL.md" in record.notes["protocol"]
    assert "warm_up" not in record.notes


@pytest.mark.parametrize(
    ("change", "lacking"),
    [
        ({"partial": True}, "partial run"),
        ({"judge_memory": {"card_peak_mib": None}}, "while the judge answered"),
        ({"runs": {"memory": {"card_peak_mib": None}}}, "while pcb1 was scored"),
        ({"judge": {"server": {}}}, "which server answered: image"),
        ({"judge": {"image_min_tokens": "unknown"}}, "minimum tokens"),
        ({"judge": {"gpu": None}}, "the card's name"),
        ({"judge": {"cold": None}}, "the cold came from the server's start"),
        ({"judge": {"warm_up": None}}, "the warm-up"),
        ({"runs": {"checkpoint": None}}, "pcb1's checkpoint"),
    ],
)
def test_what_a_final_record_lacks_is_said(
    stage2_record: BenchRecord, change: dict[str, Any], lacking: str
) -> None:
    """Each thing the protocol asks a final record to hold, taken away in turn."""
    dumped = stage2_record.model_dump(mode="json")
    for key, value in change.items():
        if key == "runs":
            pcb1 = dumped["runs"]["pcb1"]
            for inner, replaced in value.items():
                if isinstance(replaced, dict):
                    pcb1[inner].update(replaced)
                else:
                    pcb1[inner] = replaced
        elif isinstance(value, dict):
            dumped[key].update(value)
        else:
            dumped[key] = value

    missing = missing_for_final(BenchRecord.model_validate(dumped))

    assert any(lacking in reason for reason in missing), missing


def test_the_boards_of_the_parts_the_bench_does_not_score_are_week_2s_as_recorded() -> None:
    """The ruling names four boards and the bench scores two parts: the others are held to file."""
    week2 = REPOSITORY / "results" / "stage2" / "week2"
    with (week2 / "boards.csv").open(encoding="utf-8", newline="") as file:
        rows = {(row["part"], row["image_id"]): row for row in csv.DictReader(file)}
    trainings = json.loads((week2 / "run-1" / "anomaly.json").read_text(encoding="utf-8"))

    assert [(board.part, board.image_id) for board in BOARDS_NOT_SCORED_BY_THE_BENCH] == [
        ("pcb2", "bad-060"),
        ("pcb3", "bad-097"),
    ]
    for board in BOARDS_NOT_SCORED_BY_THE_BENCH:
        row = rows[(board.part, board.image_id)]
        assert board.score == float(row["xpu_run_1_score"])
        assert board.above == (row["xpu_run_1_flagged"] == "1")
        assert board.label == row["label"]
        assert (
            board.threshold
            == (trainings["categories"][board.part]["record"]["thresholds"]["image"])
        )
        assert abs(board.score - board.threshold) <= SCORE_TOLERANCE


def test_with_the_runs_two_parts_a_stage_two_record_names_the_rulings_four_boards(
    stage2_record: BenchRecord,
) -> None:
    """Those it scored and those it could not, told apart; Stage I's says nothing of the others."""
    thresholds = {"pcb1": 31.319488525390625, "pcb4": 30.048744201660156}
    boards = [
        _board("pcb1", "bad-029", 31.319490432739258),
        _board("pcb4", "bad-081", 30.048744201660156),
    ]
    found = boards_on_threshold(boards, thresholds, elsewhere=BOARDS_NOT_SCORED_BY_THE_BENCH)

    assert [board.image_id for board in found.boards] == ["bad-029", "bad-081"]
    assert [board.image_id for board in found.elsewhere] == ["bad-060", "bad-097"]
    assert boards_on_threshold(boards, thresholds).elsewhere == ()
    assert stage2_record.on_threshold is not None
    assert stage2_record.on_threshold.elsewhere == BOARDS_NOT_SCORED_BY_THE_BENCH
