"""Judge the images of a run: from the anomaly model's output to one decision per image.

For each image the anomaly model scored, its regions are taken in rank
order. Each is measured, drawn under its heatmap, put to the judge with the
clause table, and decided by the disposition rule. Judging stops at the first
rejected region, since one nonconforming area rejects the board, and at a
server that cannot be reached. The decision is written beside the anomaly
model's own sidecar:

    <run>/<image_id>/
        result.json                   the anomaly model's (read, never changed)
        decision.json                 the `Decision`
        overlays/region-001.png ...   each judged region's crop under its heatmap

This module reads the anomaly model's files itself and does not import
Anomalib, so judging an existing run starts in a second or two.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, NamedTuple, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from spec_to_inspector.anomaly.records import ImageResult, Region, RunIndex
from spec_to_inspector.anomaly.regions import upsample
from spec_to_inspector.judge.answer import AnswerError, JudgeAnswer, answer_schema, parse_answer
from spec_to_inspector.judge.client import ChatClient, Completion, Message, VlmError
from spec_to_inspector.judge.decision import (
    Cause,
    Decision,
    JudgeCall,
    RegionDecision,
    Verdict,
    combine_regions,
    decide_region,
    refer_region,
)
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.join import JoinError, calibration_for, measure_region, zone_map_for
from spec_to_inspector.judge.overlay import encode_png, heatmap_overlay
from spec_to_inspector.judge.prompt import build_messages, repair_messages
from spec_to_inspector.measure import Calibration, ZoneMap
from spec_to_inspector.spec.schema import Specification

RESULT_NAME: Final = "result.json"
RUN_INDEX_NAME: Final = "run.json"
DECISION_NAME: Final = "decision.json"
OVERLAYS_DIR: Final = "overlays"
DEFAULT_MAX_REGIONS: Final = 3

Recall = Callable[[str], Sequence[str]]
"""Recalls the engineers' corrections for a part, each rendered in words; at most three."""


class InspectError(RuntimeError):
    """A run or an image cannot be judged as asked; the message says why."""


class Asked(NamedTuple):
    """The judge's reply to one question, after validation and at most one retry.

    Attributes:
        answer: The validated answer, or None if none came.
        call: What the asking cost and returned.
        cause: Why no answer came, when none did.
    """

    answer: JudgeAnswer | None
    call: JudgeCall
    cause: Cause | None


def _call(completions: Sequence[Completion], error: str | None = None) -> JudgeCall:
    """Summarise the requests made for one question.

    Args:
        completions: The completions received, in order.
        error: Why no valid answer came, if none did.

    Returns:
        The record: the time of all requests, the counts of the last.
    """
    last = completions[-1] if completions else None
    return JudgeCall(
        attempts=max(len(completions), 1),
        seconds=sum(completion.seconds for completion in completions),
        prompt_tokens=None if last is None else last.prompt_tokens,
        completion_tokens=None if last is None else last.completion_tokens,
        cached_tokens=None if last is None else last.cached_tokens,
        tokens_per_second=None if last is None else last.tokens_per_second,
        texts=tuple(completion.text for completion in completions),
        error=error,
    )


def ask_judge(
    client: ChatClient,
    messages: Sequence[Message],
    schema: dict[str, object],
    *,
    cache_prompt: bool | None = None,
) -> Asked:
    """Ask the judge one question and validate its answer, retrying a refused answer once.

    The retry shows the model its own text and what was wrong with it. A
    second refused answer, or a server that gives no completion, ends the
    asking: nothing is guessed in the answer's place.

    Args:
        client: The VLM server's client.
        messages: The conversation built for the region.
        schema: The answer's JSON schema, for constrained decoding.
        cache_prompt: llama.cpp's per-request prompt-cache switch; None
            leaves the server's default.

    Returns:
        The validated answer, or the cause there is none, with the record of
        the requests either way.
    """
    completions: list[Completion] = []
    conversation = list(messages)
    refusal: AnswerError | None = None
    for _attempt in range(2):
        try:
            completion = client.complete(conversation, schema=schema, cache_prompt=cache_prompt)
        except VlmError as error:
            return Asked(None, _call(completions, str(error)), Cause.SERVER_UNAVAILABLE)
        completions.append(completion)
        try:
            return Asked(parse_answer(completion.text), _call(completions), None)
        except AnswerError as error:
            refusal = error
            conversation = repair_messages(messages, error)
    problem = refusal.problem if refusal is not None else "no answer"
    return Asked(None, _call(completions, problem), Cause.MALFORMED_ANSWER)


def _refused(index: int, asked: Asked, **context: object) -> RegionDecision:
    """Refer a region whose question brought no valid answer.

    Args:
        index: The region's index.
        asked: The failed asking.
        **context: The region's measurement, crop and overlay, as fields of
            the decision.

    Returns:
        The referral. A server's failure is quoted in the reason; a refused
        answer's detail stays in the call's record, since it describes the
        model's text.
    """
    reason = (
        f"the judge could not be asked: {asked.call.error}"
        if asked.cause is Cause.SERVER_UNAVAILABLE
        else "the judge's answer was not valid after one retry"
    )
    referral = refer_region(index=index, cause=asked.cause or Cause.MALFORMED_ANSWER, reason=reason)
    return referral.model_copy(update={**context, "call": asked.call})


class _Scene(NamedTuple):
    """What judging the regions of one image needs, read once.

    Attributes:
        directory: The image's directory in the run.
        result: The anomaly model's sidecar.
        labels: The label image at the source's size.
        scores: The raw anomaly map stretched to the source's size.
        calibration: The source image's scale.
        zones: The part's zones.
    """

    directory: Path
    result: ImageResult
    labels: NDArray[np.uint16]
    scores: NDArray[np.float32]
    calibration: Calibration
    zones: ZoneMap


def _read_scene(directory: Path, result: ImageResult, specification: Specification) -> _Scene:
    """Read an image's label image and anomaly map, and its part's scale and zones.

    Args:
        directory: The image's directory in the run.
        result: The anomaly model's sidecar.
        specification: The parsed specification.

    Returns:
        The scene.

    Raises:
        JoinError: If the specification has no calibration for the part, or
            the label image cannot be read.
    """
    calibration = calibration_for(
        specification, result.category, width_px=result.width, height_px=result.height
    )
    read = cv2.imread(str(directory / result.regions_image), cv2.IMREAD_UNCHANGED)
    # OpenCV's stubs promise an array, but an unreadable file yields None.
    labels = cast("NDArray[np.uint16] | None", read)
    if labels is None or labels.ndim != 2:
        msg = f"the label image {directory / result.regions_image} cannot be read"
        raise JoinError(msg)
    stored = cast("NDArray[np.float32]", np.load(directory / result.anomaly_map))
    return _Scene(
        directory=directory,
        result=result,
        labels=labels.astype(np.uint16, copy=False),
        scores=upsample(stored, width=result.width, height=result.height),
        calibration=calibration,
        zones=zone_map_for(specification, result.category),
    )


def _judge_region(
    scene: _Scene,
    region: Region,
    specification: Specification,
    client: ChatClient,
    *,
    corrections: Sequence[str],
    cache_prompt: bool | None,
    write: bool,
) -> RegionDecision:
    """Measure one region, show it to the judge and decide it.

    Args:
        scene: The image's label image, anomaly map, scale and zones.
        region: The region, as the anomaly model recorded it.
        specification: The parsed specification.
        client: The VLM server's client.
        corrections: The corrections recalled for the part.
        cache_prompt: llama.cpp's per-request prompt-cache switch.
        write: Whether to keep the overlay as a file beside the crops.

    Returns:
        The region's decision.
    """
    result = scene.result
    try:
        measurement = measure_region(scene.labels, region.index, scene.calibration, scene.zones)
    except JoinError as error:
        return refer_region(
            index=region.index,
            cause=Cause.NOT_MEASURED,
            reason=f"the flagged area could not be measured: {error}",
            from_peak=region.from_peak,
        )
    box = region.crop_box
    if region.crop is None or box is None:
        return refer_region(
            index=region.index,
            cause=Cause.NOT_JUDGED,
            reason="no crop of the flagged area was written, so the judge was not shown it",
            measurement=measurement,
            from_peak=region.from_peak,
        )

    window = (slice(box.y, box.y + box.height), slice(box.x, box.x + box.width))
    crop_png = (scene.directory / region.crop).read_bytes()
    with Image.open(scene.directory / region.crop) as opened:
        crop = np.asarray(opened.convert("RGB"))
    overlay = heatmap_overlay(
        crop,
        scene.scores[window],
        scene.labels[window] == region.index,
        low=result.region_threshold,
        high=result.map_max,
    )
    overlay_png = encode_png(overlay)
    overlay_name = f"{OVERLAYS_DIR}/region-{region.index:03d}.png"
    if write:
        (scene.directory / OVERLAYS_DIR).mkdir(exist_ok=True)
        (scene.directory / overlay_name).write_bytes(overlay_png)

    messages = build_messages(
        specification,
        result.category,
        measurement,
        crop_png=crop_png,
        overlay_png=overlay_png,
        from_peak=region.from_peak,
        corrections=corrections,
    )
    asked = ask_judge(
        client,
        messages,
        answer_schema(specification, result.category),
        cache_prompt=cache_prompt,
    )
    shown: dict[str, object] = {
        "crop": region.crop,
        "overlay": overlay_name if write else None,
        "call": asked.call,
    }
    if asked.answer is None:
        return _refused(
            region.index, asked, measurement=measurement, from_peak=region.from_peak, **shown
        )
    decided = decide_region(
        specification,
        result.category,
        index=region.index,
        measurement=measurement,
        answer=asked.answer,
        from_peak=region.from_peak,
    )
    return decided.model_copy(update=shown)


def _judge_regions(
    directory: Path,
    result: ImageResult,
    specification: Specification,
    client: ChatClient,
    *,
    max_regions: int,
    recall: Recall | None,
    cache_prompt: bool | None,
    write: bool,
) -> tuple[Verdict, list[RegionDecision]]:
    """Judge an image's regions in rank order and combine them.

    Args:
        directory: The image's directory in the run.
        result: The anomaly model's sidecar, which holds at least one region.
        specification: The parsed specification.
        client: The VLM server's client.
        max_regions: The most regions to put to the judge.
        recall: Recalls the corrections for the part, if a store exists.
        cache_prompt: llama.cpp's per-request prompt-cache switch.
        write: Whether to keep each overlay as a file.

    Returns:
        The board's verdict and the regions judged.
    """
    try:
        scene = _read_scene(directory, result, specification)
    except JoinError as error:
        referral = refer_region(
            index=result.regions[0].index,
            cause=Cause.NOT_MEASURED,
            reason=f"the flagged area could not be measured: {error}",
            from_peak=result.regions[0].from_peak,
        )
        return combine_regions([referral], found=len(result.regions)), [referral]

    corrections = tuple(recall(result.category)) if recall is not None else ()
    decided: list[RegionDecision] = []
    for region in result.regions[:max_regions]:
        decision = _judge_region(
            scene,
            region,
            specification,
            client,
            corrections=corrections,
            cache_prompt=cache_prompt,
            write=write,
        )
        decided.append(decision)
        if decision.outcome is Outcome.REJECT or decision.review_cause is Cause.SERVER_UNAVAILABLE:
            break
    return combine_regions(decided, found=len(result.regions)), decided


def _write_atomically(path: Path, text: str) -> None:
    """Write a file so that a reader never sees it half written.

    Args:
        path: The file.
        text: Its content.
    """
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def judge_image(
    directory: Path,
    specification: Specification,
    client: ChatClient,
    *,
    max_regions: int = DEFAULT_MAX_REGIONS,
    recall: Recall | None = None,
    cache_prompt: bool | None = None,
    write: bool = True,
) -> Decision:
    """Decide one image of a run, and write the decision beside its result.

    An image with no flagged area is accepted without asking the judge. An
    image with flagged areas is accepted only when every one of them was
    judged and accepted, rejected when one is rejected, and referred to an
    engineer otherwise.

    Args:
        directory: The image's directory in the run, holding `result.json`.
        specification: The parsed specification.
        client: The VLM server's client.
        max_regions: The most regions to put to the judge, in rank order.
        recall: Recalls the engineers' corrections for a part, each in words;
            the corrections store fills this, and without it the prompt's
            slot says there are none.
        cache_prompt: llama.cpp's per-request prompt-cache switch; None
            leaves the server's default.
        write: Whether to write `decision.json` and the overlays; a timing
            run asks and decides without leaving files.

    Returns:
        The decision, as written to `decision.json`.

    Raises:
        InspectError: If the directory holds no readable result, or
            `max_regions` is below one.
    """
    if max_regions < 1:
        msg = f"max_regions must be at least 1, got {max_regions}"
        raise InspectError(msg)
    try:
        result = ImageResult.model_validate_json(
            (directory / RESULT_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        msg = f"{directory} holds no readable {RESULT_NAME}: {error}"
        raise InspectError(msg) from error

    regions: list[RegionDecision] = []
    if result.regions:
        verdict, regions = _judge_regions(
            directory,
            result,
            specification,
            client,
            max_regions=max_regions,
            recall=recall,
            cache_prompt=cache_prompt,
            write=write,
        )
    elif result.predicted_anomalous:
        verdict = Verdict(
            Outcome.NEEDS_REVIEW,
            "the anomaly model flagged the board but located no area to judge; "
            "an engineer must decide",
            Cause.NOT_JUDGED,
            None,
        )
    else:
        verdict = Verdict(
            Outcome.ACCEPT,
            f"the anomaly score {result.score:.3f} is not above the threshold "
            f"{result.image_threshold:.3f}, so no area of the board was flagged",
            None,
            None,
        )

    deciding = next((r for r in regions if r.index == verdict.deciding_region), None)
    decision = Decision(
        category=result.category,
        image_id=result.image_id,
        image=result.image,
        outcome=verdict.outcome,
        reason=verdict.reason,
        review_cause=verdict.review_cause,
        deciding_region=verdict.deciding_region,
        clause=None if deciding is None else deciding.clause,
        score=result.score,
        image_threshold=result.image_threshold,
        predicted_anomalous=result.predicted_anomalous,
        regions_found=len(result.regions),
        regions=tuple(regions),
        specification=specification.title,
        judge_url=client.url,
        judge_model=client.model,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    if write:
        _write_atomically(directory / DECISION_NAME, decision.model_dump_json(indent=2) + "\n")
    return decision


def load_decision(directory: Path) -> Decision:
    """Read one image's decision.

    Args:
        directory: The image's directory in the run.

    Returns:
        The decision.
    """
    return Decision.model_validate_json((directory / DECISION_NAME).read_text(encoding="utf-8"))


def read_run_index(run_directory: Path) -> RunIndex:
    """Read a run's index.

    Args:
        run_directory: The run's directory.

    Returns:
        The index.

    Raises:
        InspectError: If the directory holds no readable `run.json`.
    """
    try:
        return RunIndex.model_validate_json(
            (run_directory / RUN_INDEX_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        msg = f"{run_directory} is not a run: no readable {RUN_INDEX_NAME} ({error})"
        raise InspectError(msg) from error


def judge_run(
    run_directory: Path,
    specification: Specification,
    client: ChatClient,
    *,
    image_ids: Sequence[str] | None = None,
    max_regions: int = DEFAULT_MAX_REGIONS,
    recall: Recall | None = None,
    cache_prompt: bool | None = None,
    on_decision: Callable[[Decision], None] | None = None,
) -> list[Decision]:
    """Decide the images of a run, one after another.

    Args:
        run_directory: The run's directory, holding `run.json`.
        specification: The parsed specification.
        client: The VLM server's client.
        image_ids: The images to judge, in this order; every image of the
            run, in the run's order, if None.
        max_regions: The most regions per image to put to the judge.
        recall: Recalls the engineers' corrections for a part.
        cache_prompt: llama.cpp's per-request prompt-cache switch.
        on_decision: Called with each decision as it is made.

    Returns:
        The decisions, in the order judged.

    Raises:
        InspectError: If the directory is not a run, or names an image the
            run does not hold.
    """
    index = read_run_index(run_directory)
    held = [entry.image_id for entry in index.entries]
    chosen = held if image_ids is None else list(image_ids)
    unknown = [image_id for image_id in chosen if image_id not in held]
    if unknown:
        msg = f"the run {run_directory} holds no image {', '.join(unknown)}"
        raise InspectError(msg)

    decisions: list[Decision] = []
    for image_id in chosen:
        decision = judge_image(
            run_directory / image_id,
            specification,
            client,
            max_regions=max_regions,
            recall=recall,
            cache_prompt=cache_prompt,
        )
        decisions.append(decision)
        if on_decision is not None:
            on_decision(decision)
    return decisions
