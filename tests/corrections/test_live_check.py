"""Tests for the scripted live check, with a fake VLM server in the real judge's place."""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from spec_to_inspector.corrections import live_check
from spec_to_inspector.corrections.live_check import (
    CorrectionsResults,
    Judgement,
    LiveCheckError,
    Pair,
    SlotPass,
    check_category,
    check_pair,
    drift,
)
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import DECISION_NAME
from spec_to_inspector.judge.timing import spread
from spec_to_inspector.spec.schema import write_clause_table
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

SPEC = specification()
PAIR = Pair(
    category="pcb9",
    misjudged="scratch",
    sibling="two",
    truth="missing",
    note="the pad is bare",
    controls=("speck",),
)
RENDERED = (
    "On a pcb9 board the judge called the flagged area 'scratch' (clause 4.1); "
    "the engineer corrected it to 'missing' (clause 4.2). The engineer's note: the pad is bare."
)


def _reply(defect_class: str | None = "scratch", clause_id: str | None = "4.1") -> str:
    return json.dumps(
        {"reason": "a mark on the board face", "defect_class": defect_class, "clause_id": clause_id}
    )


SCRATCH, MISSING, NOTHING = _reply(), _reply("missing", "4.2"), _reply(None, None)


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A run of four flagged boards and a good one, written once for the module.

    Returns:
        The run's directory.
    """
    return write_run(
        tmp_path_factory.mktemp("live-check"),
        {"good": "good", "scratch": "scratch", "speck": "speck", "two": "two", "peak": "peak"},
    )


@pytest.fixture
def store(tmp_path: Path) -> CorrectionStore:
    """An absent store.

    Returns:
        The store.
    """
    return CorrectionStore(tmp_path / "pair.sqlite3")


@pytest.fixture
def client() -> Iterator[tuple[FakeVlm, ChatClient]]:
    """A fake server that says "scratch" unless scripted, and its client.

    Yields:
        The server and the client.
    """
    with (
        FakeVlm(default=SCRATCH) as server,
        ChatClient(server.url, "fake", timeout_seconds=5.0) as chat,
    ):
        yield server, chat


def test_a_pair_is_recorded_before_and_after_under_both_strategies(
    run: Path, store: CorrectionStore
) -> None:
    """The sibling is fixed both ways; the control holds by part and is moved on the answer."""
    script = [
        SCRATCH,  # the misjudged image, before
        SCRATCH,  # the sibling, before
        SCRATCH,  # the control, before
        MISSING,  # the sibling, by part
        SCRATCH,  # the sibling, on the answer: the first question
        MISSING,  # and the second, with the correction
        SCRATCH,  # the control, by part
        SCRATCH,  # the control, on the answer: the first question
        MISSING,  # and the second
    ]
    with FakeVlm(script) as server, ChatClient(server.url, "fake", timeout_seconds=5.0) as chat:
        checked = check_pair(PAIR, run, SPEC, chat, store)

    record = checked.record
    assert len(server.requests) == len(script)
    assert (record.expected_class, record.expected_clause) == ("missing", "4.2")
    assert record.correction == RENDERED
    assert record.not_recorded is None
    assert record.misjudged_before.names("scratch", "4.1")
    assert not record.right_before
    assert record.right_by_part
    assert record.right_by_answer
    assert record.sibling_by_part is not None
    assert record.sibling_by_part.corrections == (RENDERED,)
    assert record.sibling_by_part.requests == 1
    assert not record.sibling_by_part.asked_twice
    assert record.sibling_by_answer is not None
    assert record.sibling_by_answer.asked_twice
    assert record.sibling_by_answer.requests == 2
    assert (record.sibling_by_answer.first_class, record.sibling_by_answer.first_clause) == (
        "scratch",
        "4.1",
    )
    (control,) = record.controls
    assert control.before.image_id == "speck"
    assert control.held_by_part
    assert not control.held_by_answer
    assert checked.correction is not None
    assert store.for_image("pcb9", "scratch") == [checked.correction]
    assert checked.sibling_by_part is not None
    assert checked.sibling_by_part.corrected.in_prompt
    assert list(run.glob(f"*/{DECISION_NAME}")) == [], "nothing is written into the run"


def test_an_image_the_judge_has_right_this_time_is_recorded_as_not_misjudged(
    run: Path, store: CorrectionStore
) -> None:
    """With nothing to override, the before stands alone and the record says why."""
    with (
        FakeVlm(default=MISSING) as server,
        ChatClient(server.url, "fake", timeout_seconds=5.0) as chat,
    ):
        record = check_pair(PAIR, run, SPEC, chat, store).record

    assert record.not_recorded is not None
    assert "repeats the judge's own answer" in record.not_recorded
    assert record.correction is None
    assert record.right_before
    assert record.sibling_by_part is None
    assert record.right_by_part is None
    assert record.controls == ()
    assert len(server.requests) == 3
    assert not store.path.exists()


def test_a_pair_of_good_boards_is_corrected_to_no_clause(run: Path, store: CorrectionStore) -> None:
    """The engineer calls a false alarm; right is then the judge saying no clause applies."""
    pair = Pair(category="pcb9", misjudged="scratch", sibling="speck", truth=None, note="glare")
    script = [SCRATCH, SCRATCH, NOTHING, SCRATCH, NOTHING]
    with FakeVlm(script) as server, ChatClient(server.url, "fake", timeout_seconds=5.0) as chat:
        record = check_pair(pair, run, SPEC, chat, store).record

    assert (record.expected_class, record.expected_clause) == (None, None)
    assert record.correction is not None
    assert record.correction.endswith("no defect: no clause applies. The engineer's note: glare.")
    assert record.right_by_part
    assert record.right_by_answer
    assert record.sibling_by_part is not None
    assert record.sibling_by_part.outcome is Outcome.NEEDS_REVIEW
    assert len(server.requests) == len(script)


def test_what_the_run_or_the_table_cannot_bear_stops_the_check(
    run: Path, store: CorrectionStore, client: tuple[FakeVlm, ChatClient]
) -> None:
    """An image not in the run, one with no flagged area, a type with no clause."""
    _, chat = client
    for changes, problem in [
        ({"sibling": "nowhere"}, "holds no image nowhere"),
        ({"misjudged": "good"}, "good has no flagged area"),
        ({"truth": "burnt"}, "has 0 clauses for the defect type 'burnt'"),
    ]:
        with pytest.raises(LiveCheckError, match=problem):
            check_pair(PAIR.model_copy(update=changes), run, SPEC, chat, store)


def test_a_judge_that_cannot_be_reached_stops_the_check(run: Path, store: CorrectionStore) -> None:
    """A referral for want of a server is not a before or an after."""
    with (
        ChatClient("http://127.0.0.1:9/v1", "fake", timeout_seconds=1.0) as chat,
        pytest.raises(LiveCheckError, match="could not be asked"),
    ):
        check_pair(PAIR, run, SPEC, chat, store)


def test_a_part_is_checked_pair_by_pair_then_timed_three_ways(
    run: Path, tmp_path: Path, client: tuple[FakeVlm, ChatClient]
) -> None:
    """Each pair has a store of its own; the passes share one that holds every override."""
    _, chat = client
    pair = PAIR.model_copy(update={"controls": ()})

    check = check_category("pcb9", [pair], run, SPEC, chat, tmp_path, timing_images=2)

    assert [record.pair for record in check.pairs] == [pair]
    assert check.slot_corrections == (RENDERED,)
    assert [timed.recall for timed in check.passes] == ["none", "part", "answer"]
    assert [timed.corrections_in_store for timed in check.passes] == [0, 1, 1]
    for timed in check.passes:
        assert [j.image_id for j in timed.judgements] == ["speck", "two"], "not the misjudged"
        assert timed.images == 2
        assert timed.seconds.n == 2
    empty, by_part, by_answer = check.passes
    assert all(j.corrections == () for j in empty.judgements)
    assert all(j.corrections == (RENDERED,) for j in by_part.judgements)
    assert (empty.asked_twice, by_part.asked_twice, by_answer.asked_twice) == (0, 0, 2)
    assert [moved.recall for moved in check.drift] == ["part", "answer"]
    assert CorrectionStore(tmp_path / "pcb9-pair-1.sqlite3").count() == 1
    assert CorrectionStore(tmp_path / "pcb9-together.sqlite3").count() == 1
    assert list(run.glob(f"*/{DECISION_NAME}")) == []


def test_a_part_with_no_override_recorded_is_timed_with_the_empty_slot_alone(
    run: Path, tmp_path: Path
) -> None:
    """When the judge had every "misjudged" image right, there is no correction to time."""
    with (
        FakeVlm(default=MISSING) as server,
        ChatClient(server.url, "fake", timeout_seconds=5.0) as chat,
    ):
        check = check_category("pcb9", [PAIR], run, SPEC, chat, tmp_path, timing_images=2)

    assert [timed.recall for timed in check.passes] == ["none"]
    assert check.drift == ()
    assert check.slot_corrections == ()


def test_a_run_of_another_part_or_too_small_is_refused(
    run: Path, tmp_path: Path, client: tuple[FakeVlm, ChatClient]
) -> None:
    """The passes need their images and one more to warm the cache."""
    _, chat = client
    with pytest.raises(LiveCheckError, match="is a run of part pcb9, not of pcb4"):
        check_category("pcb4", [], run, SPEC, chat, tmp_path)
    with pytest.raises(LiveCheckError, match="has 3 flagged images besides the pairs' own"):
        check_category("pcb9", [PAIR], run, SPEC, chat, tmp_path, timing_images=3)


def _said(image_id: str, label: str, truth: tuple[str, ...], named: str | None) -> Judgement:
    return Judgement(
        image_id=image_id,
        label=label,
        truth=truth,
        defect_class=named,
        clause_id=None if named is None else "5.1",
        judge_line="a line",
        outcome=Outcome.REJECT,
        review_cause=None,
        corrections=(),
        requests=1,
        asked_twice=False,
        first_class=None,
        first_clause=None,
        seconds=1.0,
        prompt_tokens=100,
        cached_tokens=50,
    )


def _pass(recall: str, named: list[str | None]) -> SlotPass:
    images = [
        ("a", "bad", ("damage",)),
        ("b", "bad", ("damage",)),
        ("c", "bad", ("burnt",)),
        ("d", "bad", ("damage", "dirt")),
        ("e", "good", ()),
        ("f", "bad", ()),
    ]
    judgements = tuple(
        _said(image_id, label, truth, name)
        for (image_id, label, truth), name in zip(images, named, strict=True)
    )
    return SlotPass(
        recall=recall,
        corrections_in_store=0,
        images=len(judgements),
        asked_twice=0,
        seconds=spread([1.0] * len(judgements)),
        prompt_tokens=None,
        cached_tokens=None,
        judgements=judgements,
    )


def test_drift_counts_what_was_fixed_and_what_was_broken() -> None:
    """Only images with one defect type are scored; good boards are counted apart."""
    before = _pass("none", ["burnt", "damage", "burnt", "dirt", "dirt", "dirt"])
    after = _pass("part", ["damage", "damage", "damage", "damage", None, "dirt"])

    moved = drift(before, after)

    assert moved.recall == "part"
    assert moved.scored == 3
    assert (moved.right_before, moved.right_after) == (2, 2)
    assert (moved.wrong_to_right, moved.right_to_wrong) == (1, 1)
    assert moved.answers_changed == 4
    assert (moved.good_boards, moved.good_cleared_before, moved.good_cleared_after) == (1, 0, 1)

    with pytest.raises(ValueError, match="not over the same images"):
        drift(before, after.model_copy(update={"judgements": after.judgements[:2]}))


@pytest.fixture
def command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run: Path) -> typer.Typer:
    """The check's command, with the settings pointed at a copy of the fake run.

    Returns:
        The command as an app.
    """
    monkeypatch.chdir(tmp_path)
    shutil.copytree(run, tmp_path / "runs" / "pcb9" / "test")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_RUNS_DIR", str(tmp_path / "runs"))
    write_clause_table(SPEC, tmp_path / "spec.json")
    (tmp_path / "pairs.json").write_text(json.dumps([PAIR.model_dump()]), encoding="utf-8")
    app = typer.Typer()
    app.command()(live_check.main)
    return app


def test_the_command_writes_the_record_and_leaves_the_settings_store_alone(
    command: typer.Typer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One command, one figures file; the store under the runs directory is not created."""
    with FakeVlm(default=SCRATCH, props={"model_alias": "fake"}) as server:
        monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_URL", server.url)
        result = CliRunner().invoke(
            command,
            [
                "--pairs",
                "pairs.json",
                "--spec",
                "spec.json",
                "--images",
                "2",
                "--results",
                "r/c.json",
            ],
        )

    assert result.exit_code == 0, result.output
    written = CorrectionsResults.model_validate_json((tmp_path / "r" / "c.json").read_text())
    assert written.judge_url == server.url
    assert written.server == {"model_alias": "fake"}
    assert written.specification == SPEC.title
    assert [check.category for check in written.categories] == ["pcb9"]
    assert written.categories[0].pairs[0].correction == RENDERED
    assert "pairs" in written.notes
    lines = result.output.splitlines()
    assert lines[0].startswith(
        "pcb9 scratch -> two (expected missing 4.2): before scratch 4.1; by part scratch 4.1; "
        "on the answer scratch 4.1"
    )
    assert lines[1].startswith("  control speck: before scratch 4.1")
    assert any(line.startswith("pcb9 answer time, part: p50 ") for line in lines)
    assert any(line.startswith("pcb9 drift, answer: 0 of 0 right before") for line in lines)
    assert lines[-1] == "Figures: r/c.json"
    assert not (tmp_path / "runs" / "corrections.sqlite3").exists()
    assert list((tmp_path / "runs").glob(f"**/{DECISION_NAME}")) == []


def test_the_command_fails_in_words_without_a_server_or_a_pair(
    command: typer.Typer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A closed port, a part with no pair, or an unreadable pairs file: exit 1, no figures."""
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("SPEC_TO_INSPECTOR_VLM_TIMEOUT_SECONDS", "1")
    runner = CliRunner()
    base = ["--spec", "spec.json", "--images", "2", "--results", "c.json"]

    down = runner.invoke(command, ["--pairs", "pairs.json", *base])
    other = runner.invoke(command, ["--pairs", "pairs.json", "--category", "pcb2", *base])
    unreadable = runner.invoke(command, ["--pairs", "nowhere.json", *base])

    assert down.exit_code == 1
    assert "could not be asked" in down.output
    assert other.exit_code == 1
    assert "no pair to check; the pairs are of pcb9" in other.output
    assert unreadable.exit_code == 1
    assert not (tmp_path / "c.json").exists()
