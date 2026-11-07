"""The bench's declared mode: one flag naming a store, the void rule narrowed, the rest the same."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from spec_to_inspector.bench import run as benching
from spec_to_inspector.bench.labels import ClauseLabel, read_labels
from spec_to_inspector.bench.paired import pair_records, read_paired, write_paired
from spec_to_inspector.bench.readme import render_stage2_readme, summary_lines
from spec_to_inspector.bench.record import (
    BenchRecord,
    DeclaredStore,
    file_ref,
    missing_for_final,
    read_record,
    same_making,
    write_record,
)
from spec_to_inspector.bench.run import BenchError, BenchPlan, ModelLoader
from spec_to_inspector.corrections.declared_store import draw_boards
from spec_to_inspector.corrections.store import CorrectionStore, Override
from spec_to_inspector.judge.decision import Decision
from spec_to_inspector.judge.disposition import Outcome
from tests.bench.bench_fakes import REPLIES, machine_probes
from tests.bench.conftest import WARM_UP, run
from tests.judge.fake_vlm import FakeVlm

ROOT = Path(__file__).parents[2]
NOTE = "the note of the small set's correction"
FINAL_RECORD = ROOT / "results" / "stage2" / "final" / "bench.json"
TRACKED_LABELS = ROOT / "eval" / "clause_labels.csv"
KEPT_FIGURE = ROOT / "results" / "stage2" / "comparison-fp8" / "paired.json"


def _one_a_part(labels: Sequence[ClauseLabel]) -> dict[str, tuple[str, ...]]:
    """Draw as the rule does, one board a part, since the small set has too few for ten.

    Args:
        labels: The small set's labels.

    Returns:
        The draw.
    """
    return draw_boards(labels, per_part=1)


@pytest.fixture(autouse=True)
def small_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the bench's draw fit the small set."""
    monkeypatch.setattr(benching, "draw_boards", _one_a_part)


def _correction(part: str, image_id: str) -> Override:
    """Make a correction for the small set.

    Args:
        part: The part.
        image_id: The board.

    Returns:
        The override.
    """
    return Override(
        category=part,
        image_id=image_id,
        region_index=1,
        judged_class="scratch",
        judged_clause="4.2" if part == "pcb1" else "5.6",
        judged_outcome=Outcome.REJECT,
        judged_reason="a mark on the board",
        corrected_class="melt" if part == "pcb1" else "missing",
        corrected_clause="4.1" if part == "pcb1" else "5.2",
        note=NOTE,
    )


@pytest.fixture
def store_file(stage2_plan: BenchPlan, tmp_path: Path) -> Path:
    """Write a store holding one correction for each board of the small set's draw.

    Returns:
        The store's file.
    """
    store = CorrectionStore(tmp_path / "declared" / "store.sqlite3")
    for part, boards in _one_a_part(read_labels(stage2_plan.labels)).items():
        store.record(_correction(part, boards[0]))
    return store.path


@pytest.fixture
def declared_plan(stage2_plan: BenchPlan, store_file: Path) -> BenchPlan:
    """Plan a Stage II run under the declared mode.

    Returns:
        The plan.
    """
    return stage2_plan.model_copy(update={"declared_store": store_file})


@pytest.fixture
def declared_record(declared_plan: BenchPlan, machine_models: ModelLoader) -> BenchRecord:
    """Run the bench under the declared mode on the small set.

    Returns:
        The run's record.
    """
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        return run(declared_plan, server, probes=machine_probes(), models=machine_models)


def _a_foreign_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a correction from nowhere stand in every prompt.

    Args:
        monkeypatch: The test's patcher.
    """
    real = benching.judge_image

    def judged(*args: object, **kwargs: object) -> Decision:
        options = {**kwargs, "recall": lambda _part: ("a line of another store",)}
        return real(*args, **options)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(benching, "judge_image", judged)


def test_without_the_flag_a_correction_in_a_prompt_still_voids_the_run(
    stage2_plan: BenchPlan, machine_models: ModelLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The protocol's rule stands on every run that names no store."""
    _a_foreign_line(monkeypatch)
    with (
        FakeVlm([WARM_UP, *REPLIES]) as server,
        pytest.raises(BenchError, match="which the protocol forbids"),
    ):
        run(stage2_plan, server, probes=machine_probes(), models=machine_models)


def test_without_the_flag_the_record_says_what_it_always_said(stage2_record: BenchRecord) -> None:
    """No new field, the same words, no line of a store."""
    written = json.loads(stage2_record.model_dump_json())
    assert "declared_store" not in written
    assert stage2_record.judge.corrections == "none recalled"
    assert stage2_record.leak.with_corrections_in_prompt == 0
    assert "no correction was recalled" in stage2_record.notes["corrections"]


def test_a_correction_from_another_store_voids_a_declared_run(
    declared_plan: BenchPlan, machine_models: ModelLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The void rule narrows; it does not go."""
    _a_foreign_line(monkeypatch)
    with (
        FakeVlm([WARM_UP, *REPLIES]) as server,
        pytest.raises(BenchError, match="from a store other than the declared one"),
    ):
        run(declared_plan, server, probes=machine_probes(), models=machine_models)


def test_the_declared_lines_stand_in_every_prompt_and_the_warm_ups(
    declared_plan: BenchPlan, machine_models: ModelLoader
) -> None:
    """Every question asked, the warm-up too, carries the part's recalled line."""
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        run(declared_plan, server, probes=machine_probes(), models=machine_models)
    assert len(server.requests) == len(REPLIES) + 1
    assert all(NOTE in json.dumps(request["messages"]) for request in server.requests)


def test_the_record_holds_the_stores_digest_and_the_recall_it_used(
    declared_record: BenchRecord, store_file: Path
) -> None:
    """The record names the store by its bytes and the recall by the product's words."""
    declared = declared_record.declared_store
    assert declared is not None
    assert declared.file.sha256 == hashlib.sha256(store_file.read_bytes()).hexdigest()
    assert (declared.strategy, declared.limit, declared.corrections) == ("part", 3, 2)
    assert declared_record.judge.corrections == "from the declared store"
    assert set(declared.excluded) == {"pcb1", "pcb4"}
    assert all(NOTE in line for lines in declared.recalled.values() for line in lines)
    assert "declared store" in declared_record.notes["corrections"]


def test_the_stores_boards_leave_every_figure_but_stay_in_the_record(
    declared_record: BenchRecord,
) -> None:
    """Figures 1 to 7 are counted without them, and each board keeps its line."""
    scores, labels = declared_record.scores, declared_record.labels
    assert (labels.images, labels.single_defect, labels.multi_defect) == (2, 1, 1)
    assert scores.headline.strict.all.n == 1
    assert scores.lenient.all.n == 1
    assert scores.anomalous.boards == 2
    assert not declared_record.partial
    assert len(declared_record.observations) == 7
    assert declared_record.leak.decisions == 7
    flagged = sum(observation.flagged for observation in declared_record.observations)
    assert declared_record.leak.with_corrections_in_prompt == flagged
    # The small set's draw: pcb1 bad-000 is flagged, pcb4 bad-001 is not.
    assert declared_record.times.flagged_images == flagged - 1


def test_a_declared_run_says_it_is_the_comparison_and_not_final(
    declared_record: BenchRecord,
) -> None:
    """`missing_for_final` names it, as it names the other comparisons."""
    reason = "the final setting: this is the corrections comparison"
    assert reason in declared_record.not_final
    assert reason in missing_for_final(declared_record)


def test_another_store_is_another_making_and_the_same_store_is_a_repeat(
    declared_record: BenchRecord, stage2_record: BenchRecord
) -> None:
    """A second run with the same store compares; against the empty store it does not."""
    assert same_making(declared_record, declared_record) == []
    assert any("the declared store" in line for line in same_making(stage2_record, declared_record))


def test_a_store_changed_during_the_run_voids_it(
    declared_plan: BenchPlan, machine_models: ModelLoader, store_file: Path
) -> None:
    """Prompts are recalled as the run goes, so a store written meanwhile is not the one named."""

    def write_a_row(line: str) -> None:
        if line.startswith("Asked the warm-up"):
            CorrectionStore(store_file).record(_correction("pcb1", "bad-000"))

    with (
        FakeVlm([WARM_UP, *REPLIES]) as server,
        pytest.raises(BenchError, match="changed during the run"),
    ):
        run(declared_plan, server, probes=machine_probes(), models=machine_models, say=write_a_row)


def test_a_store_gone_during_the_run_voids_it(
    declared_plan: BenchPlan, machine_models: ModelLoader, store_file: Path
) -> None:
    """A store with no file is an empty one, so its going would change the prompts in silence."""

    def remove_it(line: str) -> None:
        if line.startswith("Asked the warm-up"):
            store_file.unlink()

    with (
        FakeVlm([WARM_UP, *REPLIES]) as server,
        pytest.raises(BenchError, match="changed during the run"),
    ):
        run(declared_plan, server, probes=machine_probes(), models=machine_models, say=remove_it)


def test_a_store_that_is_absent_empty_or_of_other_boards_stops_before_a_question(
    stage2_plan: BenchPlan, machine_models: ModelLoader, tmp_path: Path
) -> None:
    """A declared run on the wrong store is refused before it asks anything."""
    absent = tmp_path / "absent.sqlite3"
    empty = tmp_path / "empty.sqlite3"
    empty.touch()
    other = tmp_path / "other.sqlite3"
    CorrectionStore(other).record(_correction("pcb4", "bad-090"))
    for store, why in (
        (absent, "does not exist"),
        (empty, "holds no correction"),
        (other, "outside the draw"),
    ):
        plan = stage2_plan.model_copy(update={"declared_store": store})
        with FakeVlm([WARM_UP, *REPLIES]) as server:
            with pytest.raises(BenchError, match=why):
                run(plan, server, probes=machine_probes(), models=machine_models)
            assert server.requests == []


def test_stage_one_takes_no_declared_store(plan: BenchPlan, store_file: Path) -> None:
    """The mode is this comparison's, on the machine; the laptop's record stands as measured."""
    with (
        FakeVlm(REPLIES) as server,
        pytest.raises(BenchError, match="Stage II"),
    ):
        run(plan.model_copy(update={"declared_store": store_file}), server)


def test_reading_the_store_leaves_its_bytes_as_they_were(
    declared_plan: BenchPlan, machine_models: ModelLoader, store_file: Path
) -> None:
    """Its digest is what the record holds, so a run must not write to it."""
    before = store_file.read_bytes()
    with FakeVlm([WARM_UP, *REPLIES]) as server:
        run(declared_plan, server, probes=machine_probes(), models=machine_models)
    assert store_file.read_bytes() == before


def _a_pair(final: BenchRecord, comparison: BenchRecord, tmp_path: Path) -> tuple[Path, Path]:
    """Write the two sides of a pair.

    Args:
        final: The empty store's record.
        comparison: The declared run's record.
        tmp_path: The scratch directory.

    Returns:
        The two records' files.
    """
    paths = (tmp_path / "final" / "bench.json", tmp_path / "comparison" / "bench.json")
    write_record(paths[0], final)
    write_record(paths[1], comparison)
    return paths


def test_figure_ten_leaves_out_the_stores_boards_by_the_same_readers(
    stage2_record: BenchRecord,
    declared_record: BenchRecord,
    stage2_plan_labels: Path,
    tmp_path: Path,
) -> None:
    """The table is over the boards not in the store, and says which it left out."""
    final, comparison = _a_pair(stage2_record, declared_record, tmp_path)

    paired = pair_records(final, comparison, stage2_plan_labels)

    assert (paired.strict.boards, paired.lenient.boards) == (1, 1)
    declared = declared_record.declared_store
    assert declared is not None
    assert len(paired.excluded_boards) == 2
    assert {board.split()[0] for board in paired.excluded_boards} == set(declared.excluded)
    assert any("the declared store" in line for line in paired.differences)
    assert "for the others" in paired.correction


def test_figure_ten_reads_the_answer_time_on_the_same_boards(
    stage2_record: BenchRecord,
    declared_record: BenchRecord,
    stage2_plan_labels: Path,
    tmp_path: Path,
) -> None:
    """A prompt with corrections in it is longer, so the time goes beside the figure."""
    final, comparison = _a_pair(stage2_record, declared_record, tmp_path)

    paired = pair_records(final, comparison, stage2_plan_labels)

    times = paired.answer_time
    assert times is not None
    # Five areas in the run, less pcb1 bad-000's one: pcb4 bad-001 was not flagged.
    assert times.final_seconds.n == times.comparison_seconds.n == 4
    assert times.final_prompt_tokens is not None
    assert times.comparison_prompt_tokens is not None


def test_on_the_tracked_files_the_figure_is_over_the_115_and_the_65(tmp_path: Path) -> None:
    """The real final record and the real draw give the boards the addition declares."""
    labels = read_labels(TRACKED_LABELS)
    drawn = draw_boards(labels)
    final = read_record(FINAL_RECORD)
    store = tmp_path / "store.sqlite3"
    store.touch()
    declared = DeclaredStore(
        file=file_ref(store),
        strategy="part",
        limit=3,
        corrections=14,
        excluded=drawn,
        recalled={},
    )
    comparison = tmp_path / "bench.json"
    write_record(comparison, final.model_copy(update={"declared_store": declared}))

    paired = pair_records(FINAL_RECORD, comparison, TRACKED_LABELS)

    assert (paired.strict.boards, paired.lenient.boards) == (115, 65)
    assert (paired.strict.only_final, paired.strict.only_comparison) == (0, 0)
    assert paired.strict.both_right + paired.strict.both_wrong == 115
    assert len(paired.excluded_boards) == 20
    counted = [
        row
        for row in labels
        if row.single and (row.part, row.image_id) not in declared.excluded_keys
    ]
    assert sum(row.part == "pcb1" for row in counted) == 81
    assert sum(row.part == "pcb4" for row in counted) == 34
    times = paired.answer_time
    assert times is not None
    assert times.final_seconds == times.comparison_seconds
    assert times.final_seconds.n == 197


def test_a_pair_with_no_store_writes_what_it_always_wrote(
    stage2_record: BenchRecord, stage2_plan_labels: Path, tmp_path: Path
) -> None:
    """The other comparisons' `paired.json` gains no field and loses no board."""
    final, comparison = _a_pair(stage2_record, stage2_record, tmp_path)

    paired = pair_records(final, comparison, stage2_plan_labels)
    written = json.loads(paired.model_dump_json())

    assert (paired.strict.boards, paired.lenient.boards) == (3, 1)
    assert "excluded_boards" not in written
    assert "answer_time" not in written
    assert "for three" in paired.correction


def test_a_kept_record_and_a_kept_figure_are_written_back_to_the_byte(tmp_path: Path) -> None:
    """The new fields leave the tracked files' bytes alone, which `paired.json`'s digest pins."""
    write_record(tmp_path / "bench.json", read_record(FINAL_RECORD))
    assert (tmp_path / "bench.json").read_bytes() == FINAL_RECORD.read_bytes()
    write_paired(tmp_path / "paired.json", read_paired(KEPT_FIGURE))
    assert (tmp_path / "paired.json").read_bytes() == KEPT_FIGURE.read_bytes()


def test_the_page_says_what_the_store_is_and_what_it_left_out(
    stage2_record: BenchRecord,
    declared_record: BenchRecord,
    stage2_plan_labels: Path,
    store_file: Path,
    tmp_path: Path,
) -> None:
    """The page's words for a run with a store, in place of those for an empty one."""
    final, comparison = _a_pair(stage2_record, declared_record, tmp_path)
    page = render_stage2_readme(
        declared_record, paired=pair_records(final, comparison, stage2_plan_labels)
    )

    assert "## The declared store" in page
    assert hashlib.sha256(store_file.read_bytes()).hexdigest() in page
    assert "**This run is not final.**" in page
    assert "this is the corrections comparison" in page
    assert "- The corrections store empty" not in page
    assert "the store is empty throughout" not in page
    assert "the settings' default, `part`" in page
    assert NOTE in page
    assert "left out of figures 1 to 7" in page
    assert "4 of 7 decisions had a correction in a prompt" in page
    assert "and 4 boards were flagged" in page
    assert "Left out of both tables" in page
    assert "with no correction for there being three" not in page
    assert "The answer time on the same boards" in page
    assert any("declared store" in line for line in summary_lines(declared_record))


def test_the_page_of_a_run_with_no_store_keeps_its_words(stage2_record: BenchRecord) -> None:
    """Without the flag the page says what it said."""
    page = render_stage2_readme(stage2_record)

    assert "## The declared store" not in page
    assert "- The corrections store empty" in page
    assert "the store is empty throughout" in page
