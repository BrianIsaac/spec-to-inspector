"""Tests for recall into the prompt: an override changes what the judge is shown next."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from spec_to_inspector.anomaly.infer import load_result
from spec_to_inspector.corrections.override import record_override
from spec_to_inspector.corrections.recall import RecallStrategy, StoreRecall, judge_options
from spec_to_inspector.corrections.render import render_correction
from spec_to_inspector.corrections.store import CorrectionStore, Override
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import DECISION_NAME, judge_image, judge_run
from spec_to_inspector.judge.join import calibration_for, measure_region, zone_map_for
from spec_to_inspector.judge.prompt import FACTS_OPEN, NO_CORRECTIONS, build_messages
from tests.judge.fake_vlm import FakeVlm
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

SPEC = specification()
RENDERED = (
    "On a pcb9 board the judge called the flagged area 'scratch' (clause 4.1); "
    "the engineer corrected it to 'missing' (clause 4.2). "
    "The engineer's note: the pad is bare, the part is gone."
)


def _reply(defect_class: str | None = "scratch", clause_id: str | None = "4.1") -> str:
    return json.dumps(
        {
            "reason": "a bright line on the board",
            "defect_class": defect_class,
            "clause_id": clause_id,
        }
    )


def _override(**changes: object) -> Override:
    fields: dict[str, object] = {
        "category": "pcb9",
        "image_id": "scratch",
        "region_index": 1,
        "judged_class": "scratch",
        "judged_clause": "4.1",
        "judged_outcome": Outcome.REJECT,
        "judged_reason": "a bright line on the board",
        "corrected_class": "missing",
        "corrected_clause": "4.2",
    }
    return Override.model_validate(fields | changes)


def _slot(messages: list[dict[str, Any]]) -> str:
    """Cut the corrections slot out of a request: from its heading to the measured facts."""
    text = "\n".join(part["text"] for part in messages[1]["content"] if part["type"] == "text")
    start = text.index("Corrections recorded by engineers")
    return text[text.index("\n", start) + 1 : text.index("What the inspector measured")].strip()


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A run of two flagged boards, written once for the module.

    Returns:
        The run's directory.
    """
    return write_run(tmp_path_factory.mktemp("recall"), {"scratch": "scratch", "speck": "speck"})


@pytest.fixture(autouse=True)
def _fresh(run: Path) -> Iterator[None]:
    """Remove what a test's judging wrote."""
    yield
    for written in [*run.glob(f"*/{DECISION_NAME}"), *run.glob("*/overlays/*")]:
        written.unlink()


@pytest.fixture
def store(tmp_path: Path) -> CorrectionStore:
    """An absent store.

    Returns:
        The store.
    """
    return CorrectionStore(tmp_path / "corrections.sqlite3")


def test_an_override_changes_the_next_prompt(run: Path, store: CorrectionStore) -> None:
    """Before the override the slot says none; after it, the next board's prompt quotes it."""
    recalls = StoreRecall(store)
    result = load_result(run / "speck")
    with Image.open(run / "speck" / result.regions_image) as opened:
        labels = np.asarray(opened).astype(np.uint16)
    region = measure_region(
        labels,
        1,
        calibration_for(SPEC, "pcb9", width_px=result.width, height_px=result.height),
        zone_map_for(SPEC, "pcb9"),
    )

    def next_prompt() -> list[dict[str, Any]]:
        return build_messages(  # pyright: ignore[reportReturnType]
            SPEC,
            "pcb9",
            region,
            crop_png=b"crop",
            overlay_png=b"overlay",
            corrections=recalls.for_part("pcb9"),
        )

    before = next_prompt()
    assert _slot(before) == NO_CORRECTIONS

    with (
        FakeVlm(default=_reply()) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
    ):
        judge_image(run / "scratch", SPEC, client, **judge_options(store, RecallStrategy.PART))
        record_override(
            store, run / "scratch", SPEC, clause_id="4.2", note="the pad is bare, the part is gone"
        )
        after = next_prompt()
        decision = judge_image(
            run / "speck", SPEC, client, **judge_options(store, RecallStrategy.PART)
        )

    assert _slot(after) == f"1. {RENDERED}"
    assert after[0] == before[0], "the clause prefix is the same, so the server's cache holds"
    assert _slot(server.requests[0]["messages"]) == NO_CORRECTIONS
    sent = server.requests[1]["messages"]
    assert _slot(sent) == f"1. {RENDERED}"
    text = sent[1]["content"][0]["text"]
    assert text.index(RENDERED) < text.index(FACTS_OPEN)
    assert decision.corrected.in_prompt
    assert decision.regions[0].corrections == (RENDERED,)
    assert not decision.corrected.overridden


def test_the_part_is_shown_its_latest_three_newest_first(store: CorrectionStore) -> None:
    """Recall by part renders the store's most recent three, and no other part's."""
    kept = [store.record(_override(image_id=f"bad-{n}", note=f"note {n}")) for n in range(4)]
    store.record(_override(category="pcb8", image_id="bad-9"))

    lines = StoreRecall(store).for_part("pcb9")

    assert lines == tuple(render_correction(c) for c in (kept[3], kept[2], kept[1]))
    assert StoreRecall(store).for_part("pcb7") == ()


def test_recall_on_an_answer_gives_what_was_corrected_from_that_answer(
    store: CorrectionStore,
) -> None:
    """Only the corrections made where the judge said the same are shown."""
    same = store.record(_override(image_id="bad-1"))
    store.record(
        _override(
            image_id="bad-2",
            judged_class="missing",
            judged_clause="4.2",
            corrected_class="scratch",
            corrected_clause="4.1",
        )
    )
    recalls = StoreRecall(store)

    scratch = JudgeAnswer(reason="a line", defect_class="scratch", clause_id="4.1")
    nothing = JudgeAnswer(reason="a clean board", defect_class=None, clause_id=None)

    assert recalls.for_answer("pcb9", scratch) == (render_correction(same),)
    assert recalls.for_answer("pcb9", nothing) == ()
    assert recalls.for_answer("pcb8", scratch) == ()


def test_the_empty_store_gives_the_empty_slot(run: Path, store: CorrectionStore) -> None:
    """With nothing recorded both strategies leave the prompt as it is without a store."""
    for strategy in RecallStrategy:
        with (
            FakeVlm([_reply()]) as server,
            ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
        ):
            decision = judge_image(run / "scratch", SPEC, client, **judge_options(store, strategy))

        assert len(server.requests) == 1
        assert _slot(server.requests[0]["messages"]) == NO_CORRECTIONS
        assert not decision.corrected.in_prompt
    assert not store.path.exists()


def test_the_answer_strategy_asks_again_only_where_a_correction_matches(
    run: Path, store: CorrectionStore
) -> None:
    """Two questions for the board whose first answer was corrected before; one for the other."""
    store.record(_override(image_id="earlier", note="the pad is bare, the part is gone"))

    with (
        FakeVlm([_reply(), _reply("missing", "4.2"), _reply("missing", "4.2")]) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
    ):
        first, second = judge_run(run, SPEC, client, **judge_options(store, RecallStrategy.ANSWER))

    assert len(server.requests) == 3
    assert _slot(server.requests[0]["messages"]) == NO_CORRECTIONS
    assert _slot(server.requests[1]["messages"]) == f"1. {RENDERED}"
    assert _slot(server.requests[2]["messages"]) == NO_CORRECTIONS
    assert first.regions[0].first_answer is not None
    assert first.regions[0].first_answer.clause_id == "4.1"
    assert first.clause is not None
    assert first.clause.id == "4.2"
    assert first.corrected.in_prompt
    assert not second.corrected.in_prompt


def test_the_flag_knows_an_overridden_image_under_either_strategy(
    run: Path, store: CorrectionStore
) -> None:
    """An image judged again after its override says it was overridden."""
    store.record(
        _override(
            image_id="speck",
            judged_class="missing",
            judged_clause="4.2",
            corrected_class="scratch",
            corrected_clause="4.1",
        )
    )

    for strategy in RecallStrategy:
        with (
            FakeVlm(default=_reply("missing", "4.2")) as server,
            ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
        ):
            speck, scratch = judge_run(
                run, SPEC, client, image_ids=["speck", "scratch"], **judge_options(store, strategy)
            )

        assert speck.corrected.overridden
        assert not scratch.corrected.overridden
