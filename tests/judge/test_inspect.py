"""Contract tests for the judge, end to end against a fake server on a local port.

Each test runs the real pipeline on a run directory the real inference writer
wrote: the measurement, the prompt, the HTTP request, the validation, the
disposition rule and the decision file. Only the anomaly scores and the VLM's
replies are scripted.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from spec_to_inspector.anomaly.infer import load_result
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.client import ChatClient
from spec_to_inspector.judge.decision import Cause, Decision
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.inspect import (
    DECISION_NAME,
    InspectError,
    judge_image,
    judge_run,
    load_decision,
)
from spec_to_inspector.judge.join import calibration_for, measure_region, zone_map_for
from spec_to_inspector.judge.prompt import (
    FACTS_CLOSE,
    FACTS_OPEN,
    NO_CORRECTIONS,
    measured_facts,
)
from spec_to_inspector.measure import MeasuredRegion
from tests.judge.fake_vlm import FakeVlm, Reply
from tests.judge.run_fakes import write_run
from tests.spec.spec_fakes import specification

SPEC = specification()


def _reply(defect_class: str | None = "scratch", clause_id: str | None = "4.1") -> str:
    return json.dumps(
        {
            "reason": "a thin bright line scored across the board face",
            "defect_class": defect_class,
            "clause_id": clause_id,
        }
    )


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A run of one board of each kind, written once for the module.

    Returns:
        The run's directory.
    """
    return write_run(
        tmp_path_factory.mktemp("judge"),
        {"good": "good", "speck": "speck", "scratch": "scratch", "two": "two", "peak": "peak"},
    )


@pytest.fixture(autouse=True)
def _fresh(run: Path) -> Iterator[None]:
    """Remove what a test's judging wrote, so each test starts from the anomaly model's output."""
    yield
    for written in [*run.glob(f"*/{DECISION_NAME}"), *run.glob("*/overlays/*")]:
        written.unlink()


def _measured(run: Path, image_id: str, index: int = 1) -> MeasuredRegion:
    """Measure a region independently of the code under test."""
    result = load_result(run / image_id)
    with Image.open(run / image_id / result.regions_image) as opened:
        labels = np.asarray(opened).astype(np.uint16)
    calibration = calibration_for(SPEC, "pcb9", width_px=result.width, height_px=result.height)
    return measure_region(labels, index, calibration, zone_map_for(SPEC, "pcb9"))


def _judge(run: Path, image_id: str, server: FakeVlm, **options: Any) -> Decision:  # noqa: ANN401
    with ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client:
        return judge_image(run / image_id, SPEC, client, **options)


def _request_text(request: dict[str, Any]) -> str:
    return "\n".join(
        part["text"] for part in request["messages"][1]["content"] if part["type"] == "text"
    )


def test_a_valid_answer_gives_a_decision_with_the_clause_quoted(run: Path) -> None:
    """A scratch over its zone's limit is rejected, citing the row code chose."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server)

    measured = _measured(run, "scratch")
    assert decision.outcome is Outcome.REJECT
    assert decision.review_cause is None
    assert decision.deciding_region == 1
    assert decision.clause is not None
    assert decision.clause.id == "4.1.1"
    assert decision.clause.source_text == "A scratch longer than the limit of its zone is rejected."
    assert decision.reason == (
        f"region 1: longest extent {measured.longest_extent_mm:.2f} mm exceeds the 0.5 mm "
        "limit of clause 4.1.1 in zone A"
    )
    (region,) = decision.regions
    assert region.measurement == measured
    assert region.rule is not None
    assert region.rule.measured == measured.longest_extent_mm
    assert region.rule.limit == 0.5
    assert region.answer is not None
    assert region.answer.clause_id == "4.1"
    assert region.call is not None
    assert region.call.attempts == 1
    assert decision.category == "pcb9"
    assert decision.image_id == "scratch"
    assert decision.judge_url == server.url
    assert decision.judge_model == "fake-vlm"
    assert decision.specification == SPEC.title


def test_the_decision_is_written_beside_the_anomaly_models_result(run: Path) -> None:
    """`decision.json` sits next to `result.json`, with the overlay the judge was shown."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server)

    assert load_decision(run / "scratch") == decision
    assert (run / "scratch" / "result.json").is_file()
    (region,) = decision.regions
    assert region.crop == "crops/region-001.png"
    assert region.overlay == "overlays/region-001.png"
    with Image.open(run / "scratch" / "overlays" / "region-001.png") as opened:
        overlay = np.asarray(opened.convert("RGB"))
    with Image.open(run / "scratch" / "crops" / "region-001.png") as opened:
        crop = np.asarray(opened.convert("RGB"))
    assert overlay.shape == crop.shape
    assert not np.array_equal(overlay, crop)


def test_the_request_carries_the_schema_the_crop_and_the_overlay(run: Path) -> None:
    """The server is asked once, with constrained output and two images."""
    with FakeVlm([_reply()]) as server:
        _judge(run, "scratch", server)

    (request,) = server.requests
    assert request["model"] == "fake-vlm"
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["clause_id"] == {"enum": ["4.1", "4.2", None]}
    images = [p for p in request["messages"][1]["content"] if p["type"] == "image_url"]
    assert len(images) == 2
    assert images[0] != images[1]
    assert "cache_prompt" not in request


def test_the_measured_facts_in_the_prompt_are_the_measurements_numbers_verbatim(run: Path) -> None:
    """What the model is told was measured is exactly what U4's code measured."""
    with FakeVlm([_reply()]) as server:
        _judge(run, "scratch", server)

    text = _request_text(server.requests[0])
    facts = json.loads(text[text.index(FACTS_OPEN) + len(FACTS_OPEN) : text.index(FACTS_CLOSE)])
    measured = _measured(run, "scratch")
    assert facts == measured_facts(measured, from_peak=False)
    assert facts["longest_extent_mm"] == measured.longest_extent_mm
    assert facts["area_mm2"] == measured.area_mm2
    assert facts["zone"] == measured.zone == "A"


def test_an_unknown_clause_is_needs_review_without_a_retry(run: Path) -> None:
    """A clause that does not exist is an engineer's to settle, not the model's to try again."""
    with FakeVlm([_reply("scratch", "9.9")]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.MISSING_CLAUSE
    assert "clause 9.9 is not in the specification" in decision.reason
    assert decision.clause is None
    assert len(server.requests) == 1


def test_a_class_that_does_not_match_its_clause_is_needs_review(run: Path) -> None:
    """The class named must be the class of the clause cited."""
    with FakeVlm([_reply("missing", "4.1")]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.CLASS_MISMATCH
    assert "named 'missing', but clause 4.1.1 covers 'scratch'" in decision.reason
    assert len(server.requests) == 1


def test_malformed_json_is_retried_once_and_a_good_second_answer_stands(run: Path) -> None:
    """The retry shows the model its own text and the fault, and its answer is then used."""
    with FakeVlm(["The board is scratched.", _reply()]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.outcome is Outcome.REJECT
    first, second = server.requests
    assert second["messages"][:2] == first["messages"]
    assert second["messages"][2] == {"role": "assistant", "content": "The board is scratched."}
    assert "not valid" in second["messages"][3]["content"]
    (region,) = decision.regions
    assert region.call is not None
    assert region.call.attempts == 2
    assert region.call.texts == ("The board is scratched.", _reply())
    assert region.call.error is None


def test_malformed_json_twice_is_needs_review(run: Path) -> None:
    """One retry, then an engineer; never a third request and never a guess."""
    with FakeVlm(["not json", '{"reason": "still not the schema"}', _reply()]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.MALFORMED_ANSWER
    assert decision.reason == (
        "region 1: the judge's answer was not valid after one retry; an engineer must decide"
    )
    assert len(server.requests) == 2
    (region,) = decision.regions
    assert region.answer is None
    assert region.rule is None
    assert region.measurement == _measured(run, "scratch")
    assert region.call is not None
    assert region.call.attempts == 2
    assert region.call.texts == ("not json", '{"reason": "still not the schema"}')
    assert region.call.error is not None
    assert "clause_id" in region.call.error


def test_the_server_down_is_needs_review_with_the_cause(run: Path) -> None:
    """A closed port refers the board, and the reason says the judge could not be reached."""
    with FakeVlm() as server:
        url = server.url
    with ChatClient(url, "fake-vlm", timeout_seconds=5.0) as client:
        decision = judge_image(run / "two", SPEC, client)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.SERVER_UNAVAILABLE
    assert decision.reason.startswith(
        f"region 1: the judge could not be asked: cannot reach the VLM server at {url}"
    )
    assert decision.reason.endswith("; an engineer must decide")
    assert len(decision.regions) == 1
    assert decision.regions_not_judged == 1
    assert load_decision(run / "two") == decision


def test_a_server_error_is_needs_review_with_the_status(run: Path) -> None:
    """An HTTP error is the same referral, with what the server said."""
    with FakeVlm([Reply(status=503, body='{"error": {"message": "loading model"}}')]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.review_cause is Cause.SERVER_UNAVAILABLE
    assert "HTTP 503" in decision.reason
    assert "loading model" in decision.reason


def _floats(value: object) -> set[float]:
    """Collect every float anywhere in a decoded JSON value."""
    if isinstance(value, float):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_floats(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_floats(item) for item in value))
    return set()


@pytest.mark.parametrize(
    "extra",
    [
        {"measured": 99.5},
        {"limit": 0.01},
        {"longest_extent_mm": 99.5},
        {"outcome": "accept"},
    ],
)
def test_a_number_or_a_verdict_offered_by_the_model_is_refused(
    run: Path, extra: dict[str, object]
) -> None:
    """An answer that carries anything beyond its three fields never reaches a decision."""
    smuggled = json.dumps(json.loads(_reply()) | extra)
    with FakeVlm([smuggled, smuggled]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.MALFORMED_ANSWER
    assert 99.5 not in _floats(decision.model_dump(mode="json"))
    assert 0.01 not in _floats(decision.model_dump(mode="json"))


def test_a_figure_in_the_models_sentence_is_refused(run: Path) -> None:
    """The model's reason may not state a size; an answer that does is sent back, then referred."""
    sized = json.dumps(json.loads(_reply()) | {"reason": "a scratch about 0.2 mm long"})
    with FakeVlm([sized, sized]) as server:
        decision = _judge(run, "scratch", server)

    assert decision.review_cause is Cause.MALFORMED_ANSWER
    assert "0.2" not in decision.reason
    assert decision.regions[0].answer is None


def test_every_number_in_a_decision_is_the_measurements_the_clauses_or_the_anomaly_models(
    run: Path,
) -> None:
    """Outside the record of the call itself, no float exists that code did not measure or read."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server)

    dumped = decision.model_dump(mode="json")
    for region in dumped["regions"]:
        region["call"] = None
    result = load_result(run / "scratch")
    measured = _measured(run, "scratch")
    allowed = (
        _floats(measured.model_dump(mode="json"))
        | _floats(SPEC.model_dump(mode="json"))
        | {result.score, result.image_threshold}
    )
    assert _floats(dumped) <= allowed
    assert all(not any(c.isdigit() for c in r.answer.reason) for r in decision.regions if r.answer)


def test_a_board_the_anomaly_model_passed_is_accepted_without_asking(run: Path) -> None:
    """No flagged area, no question: the accept quotes the score and the threshold."""
    with FakeVlm() as server:
        decision = _judge(run, "good", server)

    assert decision.outcome is Outcome.ACCEPT
    assert decision.reason == (
        "the anomaly score 10.000 is not above the threshold 30.000, so no area of the board "
        "was flagged"
    )
    assert decision.regions == ()
    assert decision.deciding_region is None
    assert decision.clause is None
    assert server.requests == []
    assert load_decision(run / "good") == decision


def test_a_small_defect_under_its_zones_limit_is_accepted(run: Path) -> None:
    """The same class in the lenient zone, under that zone's limit, is conforming."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "speck", server)

    assert decision.outcome is Outcome.ACCEPT
    assert decision.clause is not None
    assert decision.clause.id == "4.1.2"
    assert decision.reason.startswith("every flagged area is within its clause; region 1: ")


def test_judging_stops_at_the_first_reject(run: Path) -> None:
    """Region 1 accepted, region 2 rejected: two questions, and the board is rejected on 2."""
    with FakeVlm([_reply(), _reply(), _reply()]) as server:
        decision = _judge(run, "two", server)

    assert [r.outcome for r in decision.regions] == [Outcome.ACCEPT, Outcome.REJECT]
    assert decision.outcome is Outcome.REJECT
    assert decision.deciding_region == 2
    assert decision.clause is not None
    assert decision.clause.id == "4.1.1"
    assert len(server.requests) == 2

    with FakeVlm([_reply("missing", "4.2"), _reply()]) as server:
        decision = _judge(run, "two", server)

    assert decision.outcome is Outcome.REJECT
    assert decision.deciding_region == 1
    assert len(server.requests) == 1
    assert decision.regions_not_judged == 1


def test_regions_beyond_the_limit_are_not_judged_and_refer_the_board(run: Path) -> None:
    """An accept needs every flagged area judged."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "two", server, max_regions=1)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.NOT_JUDGED
    assert decision.regions_not_judged == 1
    assert len(server.requests) == 1


def test_a_peak_patch_is_shown_without_a_size_and_not_held_to_a_limit(run: Path) -> None:
    """The fallback region's place is told, its size is not, and a sized clause refers it."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "peak", server)

    text = _request_text(server.requests[0])
    facts = json.loads(text[text.index(FACTS_OPEN) + len(FACTS_OPEN) : text.index(FACTS_CLOSE)])
    assert facts["size_measured"] is False
    assert "longest_extent_mm" not in facts
    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.NOT_MEASURED
    assert decision.regions[0].from_peak


def test_recalled_corrections_fill_the_slot(run: Path) -> None:
    """What the corrections store recalls for the part is in the request, before the facts."""
    recalled: list[str] = []

    def recall(category: str) -> list[str]:
        recalled.append(category)
        return ["A bright line on the board face is a scratch, clause 4.1."]

    with FakeVlm([_reply()]) as server:
        _judge(run, "scratch", server, recall=recall)

    text = _request_text(server.requests[0])
    assert recalled == ["pcb9"]
    assert "1. A bright line on the board face is a scratch, clause 4.1." in text
    assert text.index("1. A bright line") < text.index(FACTS_OPEN)


def test_the_prompt_cache_switch_reaches_the_request(run: Path) -> None:
    """The timing run can ask the server to evaluate the whole prompt afresh."""
    with FakeVlm([_reply()]) as server:
        _judge(run, "scratch", server, cache_prompt=False)

    assert server.requests[0]["cache_prompt"] is False


def test_a_part_the_specification_does_not_cover_is_referred_without_asking(
    run: Path, tmp_path: Path
) -> None:
    """With no calibration nothing can be measured, so nothing is asked."""
    other = specification(
        calibrations=(SPEC.calibrations[0].model_copy(update={"category": "pcb7"}),),
        zones=tuple(z.model_copy(update={"category": "pcb7"}) for z in SPEC.zones),
        clauses=tuple(c.model_copy(update={"category": "pcb7"}) for c in SPEC.clauses),
    )
    with FakeVlm() as server, ChatClient(server.url, "fake-vlm") as client:
        decision = judge_image(run / "scratch", other, client)

    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.NOT_MEASURED
    assert "no calibration for part pcb9" in decision.reason
    assert server.requests == []


def test_a_region_without_a_crop_is_referred(tmp_path: Path) -> None:
    """A run whose crops were limited leaves regions the judge cannot be shown."""
    limited = write_run(tmp_path, {"two": "two"}, max_crops=1)
    with FakeVlm([_reply(), _reply()]) as server:
        decision = _judge(limited, "two", server)

    assert [r.outcome for r in decision.regions] == [Outcome.ACCEPT, Outcome.NEEDS_REVIEW]
    assert decision.regions[1].review_cause is Cause.NOT_JUDGED
    assert "no crop" in decision.regions[1].reason
    assert len(server.requests) == 1


def test_a_run_is_judged_image_by_image_in_its_own_order(run: Path) -> None:
    """Every image of `run.json` gets a decision file; each is reported as it is made."""
    seen: list[str] = []
    with FakeVlm(default=_reply()) as server, ChatClient(server.url, "fake-vlm") as client:
        decisions = judge_run(run, SPEC, client, on_decision=lambda d: seen.append(d.image_id))

    assert [d.image_id for d in decisions] == ["good", "speck", "scratch", "two", "peak"]
    assert seen == ["good", "speck", "scratch", "two", "peak"]
    assert [d.outcome for d in decisions] == [
        Outcome.ACCEPT,
        Outcome.ACCEPT,
        Outcome.REJECT,
        Outcome.REJECT,
        Outcome.NEEDS_REVIEW,
    ]
    for decision in decisions:
        assert load_decision(run / decision.image_id) == decision


def test_a_run_can_be_judged_in_part(run: Path) -> None:
    """Named images only, in the order named."""
    with FakeVlm(default=_reply()) as server, ChatClient(server.url, "fake-vlm") as client:
        decisions = judge_run(run, SPEC, client, image_ids=["scratch", "good"])

    assert [d.image_id for d in decisions] == ["scratch", "good"]
    assert not (run / "speck" / DECISION_NAME).exists()


def test_an_image_the_run_does_not_hold_is_an_error(run: Path) -> None:
    """A mistyped image id fails before anything is judged."""
    with (
        FakeVlm(default=_reply()) as server,
        ChatClient(server.url, "fake-vlm") as client,
        pytest.raises(InspectError, match="nowhere"),
    ):
        judge_run(run, SPEC, client, image_ids=["scratch", "nowhere"])

    assert server.requests == []


def test_a_directory_that_is_not_a_run_is_an_error(tmp_path: Path) -> None:
    """A path without `run.json` is named in the error."""
    with (
        FakeVlm() as server,
        ChatClient(server.url, "fake-vlm") as client,
        pytest.raises(InspectError, match=r"run\.json"),
    ):
        judge_run(tmp_path, SPEC, client)


def test_a_run_whose_anomaly_map_is_gone_is_referred_not_crashed(tmp_path: Path) -> None:
    """A missing or unreadable file of the anomaly model refers the board, with the cause."""
    damaged = write_run(tmp_path, {"scratch": "scratch", "speck": "speck"})
    (damaged / "scratch" / "anomaly_map.npy").unlink()
    (damaged / "speck" / "regions.png").write_bytes(b"not a png")

    with FakeVlm(default=_reply()) as server:
        gone = _judge(damaged, "scratch", server)
        corrupt = _judge(damaged, "speck", server)

    for decision in (gone, corrupt):
        assert decision.outcome is Outcome.NEEDS_REVIEW
        assert decision.review_cause is Cause.NOT_MEASURED
        assert "could not be measured" in decision.reason
    assert server.requests == []


def test_a_crop_that_is_gone_or_not_its_boxs_size_is_referred(tmp_path: Path) -> None:
    """The judge is only shown a crop that is the rectangle the sidecar says it is."""
    damaged = write_run(tmp_path, {"scratch": "scratch", "speck": "speck", "two": "two"})
    (damaged / "scratch" / "crops" / "region-001.png").unlink()
    (damaged / "speck" / "crops" / "region-001.png").write_bytes(b"not a png")
    Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(
        damaged / "two" / "crops" / "region-001.png"
    )

    with FakeVlm(default=_reply()) as server:
        decisions = [_judge(damaged, name, server) for name in ("scratch", "speck", "two")]

    for decision in decisions:
        first = decision.regions[0]
        assert first.outcome is Outcome.NEEDS_REVIEW
        assert first.review_cause is Cause.NOT_JUDGED
        assert "crop" in first.reason
        assert first.call is None
        assert first.measurement is not None
    assert decisions[2].outcome is Outcome.REJECT
    assert decisions[2].deciding_region == 2
    assert len(server.requests) == 1


def test_a_retry_that_the_server_fails_counts_both_requests(run: Path) -> None:
    """A refused answer and then a failing server is two requests sent, and the server's fault."""
    failing = Reply(status=500, body='{"error": {"message": "out of memory"}}')
    with FakeVlm(["not json", failing]) as server:
        decision = _judge(run, "scratch", server)

    (region,) = decision.regions
    assert region.review_cause is Cause.SERVER_UNAVAILABLE
    assert region.call is not None
    assert region.call.attempts == 2
    assert region.call.texts == ("not json",)
    assert len(server.requests) == 2


CORRECTION = (
    "On a pcb9 board the judge called the flagged area 'scratch' (clause 4.1); "
    "the engineer corrected it to 'missing' (clause 4.2)."
)


def test_a_decision_judged_without_corrections_is_not_flagged(run: Path) -> None:
    """With nothing recalled, the flag is down and no region carries a correction."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server)

    assert not decision.corrected.in_prompt
    assert not decision.corrected.overridden
    assert decision.regions[0].corrections == ()
    assert decision.regions[0].first_answer is None
    assert load_decision(run / "scratch").corrected == decision.corrected


def test_a_correction_in_the_prompt_raises_the_flag_and_is_kept_on_the_region(run: Path) -> None:
    """The decision says a correction was shown, and quotes the lines the judge read."""
    with FakeVlm([_reply("missing", "4.2")]) as server:
        decision = _judge(run, "scratch", server, recall=lambda _: [CORRECTION])

    assert decision.corrected.in_prompt
    assert decision.regions[0].corrections == (CORRECTION,)
    assert load_decision(run / "scratch") == decision


def test_a_board_passed_by_the_anomaly_model_is_not_flagged_by_a_recall(run: Path) -> None:
    """No question was asked, so no correction was in a prompt."""
    with FakeVlm() as server:
        decision = _judge(run, "good", server, recall=lambda _: [CORRECTION])

    assert not decision.corrected.in_prompt
    assert server.requests == []


def test_an_image_an_engineer_overrode_says_so_when_judged_again(run: Path) -> None:
    """The flag's other half is asked of the store, by part and image."""
    asked: list[tuple[str, str]] = []

    def overridden(category: str, image_id: str) -> bool:
        asked.append((category, image_id))
        return image_id == "scratch"

    with FakeVlm(default=_reply()) as server:
        scratch = _judge(run, "scratch", server, overridden=overridden)
        speck = _judge(run, "speck", server, overridden=overridden)

    assert scratch.corrected.overridden
    assert not scratch.corrected.in_prompt
    assert not speck.corrected.overridden
    assert asked == [("pcb9", "scratch"), ("pcb9", "speck")]


def test_corrections_recalled_on_the_answer_bring_a_second_question(run: Path) -> None:
    """The judge answers, is shown the corrections for that answer, and its second answer stands."""
    recalled: list[tuple[str, str | None, str | None]] = []

    def on_answer(category: str, answer: JudgeAnswer) -> list[str]:
        recalled.append((category, answer.defect_class, answer.clause_id))
        return [CORRECTION]

    with FakeVlm([_reply(), _reply("missing", "4.2")]) as server:
        decision = _judge(run, "scratch", server, recall_on_answer=on_answer)

    (region,) = decision.regions
    assert recalled == [("pcb9", "scratch", "4.1")]
    assert len(server.requests) == 2
    assert NO_CORRECTIONS in _request_text(server.requests[0])
    assert f"1. {CORRECTION}" in _request_text(server.requests[1])
    assert region.first_answer is not None
    assert region.first_answer.clause_id == "4.1"
    assert region.first_call is not None
    assert region.first_call.attempts == 1
    assert region.answer is not None
    assert region.answer.clause_id == "4.2"
    assert region.clause is not None
    assert region.clause.id == "4.2"
    assert region.corrections == (CORRECTION,)
    assert decision.corrected.in_prompt
    assert decision.outcome is Outcome.REJECT


def test_no_correction_on_record_for_the_answer_means_one_question(run: Path) -> None:
    """The second question is asked only when there is something to show."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server, recall_on_answer=lambda *_: [])

    assert len(server.requests) == 1
    assert decision.regions[0].first_answer is None
    assert decision.regions[0].corrections == ()
    assert not decision.corrected.in_prompt


def test_an_answer_that_never_came_recalls_nothing(run: Path) -> None:
    """With no valid answer there is nothing to recall on."""
    called: list[str] = []

    def on_answer(category: str, answer: JudgeAnswer) -> list[str]:
        called.append(category)
        return [CORRECTION]

    with FakeVlm(["not json", "still not json"]) as server:
        decision = _judge(run, "scratch", server, recall_on_answer=on_answer)

    assert called == []
    assert decision.review_cause is Cause.MALFORMED_ANSWER


def test_a_second_question_the_server_fails_refers_the_region_and_keeps_the_first_answer(
    run: Path,
) -> None:
    """Nothing is guessed: the first answer is on record, but it does not decide."""
    with FakeVlm([_reply(), Reply(status=500, body="{}")]) as server:
        decision = _judge(run, "scratch", server, recall_on_answer=lambda *_: [CORRECTION])

    (region,) = decision.regions
    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert decision.review_cause is Cause.SERVER_UNAVAILABLE
    assert region.answer is None
    assert region.first_answer is not None
    assert region.first_answer.clause_id == "4.1"


def test_a_run_passes_both_recalls_and_the_flag_to_every_image(run: Path) -> None:
    """`judge_run` hands the corrections' callables on."""
    with (
        FakeVlm(default=_reply()) as server,
        ChatClient(server.url, "fake-vlm", timeout_seconds=5.0) as client,
    ):
        decisions = judge_run(
            run,
            SPEC,
            client,
            image_ids=["scratch", "speck"],
            recall=lambda _: [CORRECTION],
            recall_on_answer=lambda *_: [],
            overridden=lambda *_: True,
        )

    assert all(d.corrected.in_prompt and d.corrected.overridden for d in decisions)


def test_a_decision_written_before_the_flag_existed_still_reads(run: Path) -> None:
    """The runs U5 judged hold decisions without the new fields; they read as not corrected."""
    with FakeVlm([_reply()]) as server:
        decision = _judge(run, "scratch", server)
    path = run / "scratch" / DECISION_NAME
    old = json.loads(path.read_text(encoding="utf-8"))
    del old["corrected"]
    for region in old["regions"]:
        del region["corrections"], region["first_answer"], region["first_call"]
    path.write_text(json.dumps(old), encoding="utf-8")

    assert load_decision(run / "scratch") == decision
