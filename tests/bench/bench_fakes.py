"""Fakes for the bench's tests: hand-made labels and observations, and a small VisA to run on."""

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

from spec_to_inspector.anomaly.ground_truth import VISA_MASK_VALUES
from spec_to_inspector.anomaly.infer import InferenceItem, Scorer, run_inference, visa_test_items
from spec_to_inspector.anomaly.records import InferenceOptions, RunIndex
from spec_to_inspector.bench.labels import (
    ClauseLabel,
    Region1,
    derive_labels,
    read_region_truth,
    write_labels,
)
from spec_to_inspector.bench.mapping import expected_headings, mapping_row
from spec_to_inspector.bench.observe import Area, Citation, Observation
from spec_to_inspector.bench.run import LoadedModel, Probes
from spec_to_inspector.judge.decision import Cause
from spec_to_inspector.judge.disposition import Outcome
from spec_to_inspector.judge.timing import GpuReading
from tests.judge.run_fakes import _RED as RED
from tests.judge.run_fakes import HEIGHT, WIDTH, Kind, StubScorer


def label(part: str, number: int, *types: str, under: tuple[str, ...] | None = None) -> ClauseLabel:
    """Build a row of the labelled set.

    Args:
        part: The part.
        number: The image's number, which names it.
        *types: The VisA defect types of the image.
        under: The types under region 1; None for an image with no region.

    Returns:
        The label.
    """
    status = (
        Region1.NO_REGION
        if under is None
        else Region1.OFF_DEFECT
        if not under
        else Region1.ONE_TYPE
        if len(under) == 1
        else Region1.SEVERAL_TYPES
    )
    return ClauseLabel(
        part=part,
        image_id=f"bad-{number:03d}",
        visa_image=f"{part}/Data/Images/Anomaly/{number:03d}.JPG",
        anno_line=number + 2,
        visa_types=types,
        defects="single" if len(types) == 1 else "multi",
        expected_headings=expected_headings(part, types),
        region1=status,
        region1_types=under or (),
        region1_headings=expected_headings(part, under or ()),
    )


def seen(
    part: str,
    image_id: str,
    cited: str | None = None,
    *,
    kind: Literal["good", "bad"] = "bad",
    citation: Citation | None = None,
    under: tuple[str, ...] | None = (),
    outcome: Outcome = Outcome.REJECT,
    cause: Cause | None = None,
    row: str | None = None,
    named: str | None = None,
    more_areas: tuple[Area, ...] = (),
    seconds: float = 3.0,
) -> Observation:
    """Build what the bench saw of one image.

    Args:
        part: The part.
        image_id: The image's id in the run.
        cited: The VisA type whose heading the judge cited on region 1.
        kind: The image's ground truth.
        citation: The state of region 1's citation, when it is not a cited
            heading; `Citation.NOT_FLAGGED` makes an image with no region.
        under: The types under region 1 in the bench's own inference.
        outcome: The board's outcome, and region 1's.
        cause: Why the board, and region 1, is referred.
        row: The row of the clause table code applied to region 1.
        named: The class the model named, when it is not its heading's own.
        more_areas: Areas judged after region 1.
        seconds: The VLM's time on region 1.

    Returns:
        The observation.
    """
    state = citation or (Citation.CITED if cited is not None else Citation.NO_CLAUSE)
    flagged = state is not Citation.NOT_FLAGGED
    asked = state in (Citation.CITED, Citation.NO_CLAUSE, Citation.NO_ANSWER)
    heading = mapping_row(part, cited).heading_id if cited is not None else None
    first = Area(
        index=1,
        outcome=outcome,
        review_cause=cause,
        asked=asked,
        seconds=seconds if asked else None,
        attempts=1 if asked else 0,
        prompt_tokens=4700 if asked else None,
        completion_tokens=40 if asked else None,
        tokens_per_second=64.0 if asked else None,
    )
    areas = (first, *more_areas) if flagged else ()
    return Observation(
        part=part,
        image_id=image_id,
        label=kind,
        score=40.0 if flagged else 10.0,
        flagged=flagged,
        regions_found=len(areas),
        region1_types=under if flagged else None,
        citation=state,
        cited_heading=heading,
        cited_class=named or cited,
        sentence="a mark on the board" if asked and state is not Citation.NO_ANSWER else None,
        row_id=row,
        outcome=outcome if flagged else Outcome.ACCEPT,
        review_cause=cause if flagged else None,
        areas=areas,
        corrections_in_prompt=False,
        judge_seconds=(sum(area.seconds or 0.0 for area in areas) + 0.25) if flagged else 0.001,
    )


BAR = (slice(360, 410), slice(380, 600))
"""Rows and columns of the mask under the stub's long bar, in a 1000 by 800 image."""
SPECK = (slice(20, 50), slice(880, 920))
"""Rows and columns of the mask under the stub's speck, outside every zone of both parts."""

BOARDS: dict[str, tuple[tuple[str, Kind, dict[str, tuple[slice, slice]]], ...]] = {
    "pcb1": (("melt", "scratch", {"melt": BAR}),),
    "pcb4": (
        ("scratch", "scratch", {"scratch": BAR}),
        ("missing", "good", {"missing": BAR}),
        ("burnt,dirt", "two", {"dirt": SPECK, "burnt": BAR}),
    ),
}
"""Per part, each anomalous image: VisA's label, what the stub sees, and its mask by type."""

RELEASED: list[str] = []
"""The parts whose stub model has been released, in order; a test clears it first."""

GOOD: dict[str, tuple[Kind, ...]] = {"pcb1": ("good",), "pcb4": ("good", "speck")}
"""Per part, what the stub sees on each good test board; a speck is a false alarm."""


def _answer(defect_class: str | None, clause_id: str | None, reason: str) -> str:
    return json.dumps({"reason": reason, "defect_class": defect_class, "clause_id": clause_id})


REPLIES: tuple[str, ...] = (
    _answer("melt", "4.1", "a lump of solder bridges two header pins"),
    _answer("dirt", "5.1", "a small dark speck near the edge of the frame"),
    _answer("scratch", "5.6", "a long bright line scored across the board"),
    _answer(None, None, "nothing but the fixture is visible here"),
    _answer("burnt", "5.7", "a charred component with a dark halo"),
)
"""The fake judge's answers, in the order the bench asks: pcb1 then pcb4, in the split's order."""


def _flat(kind: Kind) -> Image.Image:
    colour = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    colour[..., 0] = RED[kind]
    colour[..., 1] = 110
    return Image.fromarray(colour)


def write_bench_visa(root: Path) -> None:
    """Write a small VisA of pcb1 and pcb4 that the stub scorer can tell apart.

    Each image is a flat colour whose red level names the board's kind to the
    stub; each anomalous image has a mask carrying VisA's own value for each
    of its defect types where the stub will flag an area.

    Args:
        root: The dataset directory to write.
    """
    split_rows = [["object", "split", "label", "image", "mask"]]
    for part, boards in BOARDS.items():
        annotations = [["image", "label", "mask"]]
        values = {name: value for value, name in VISA_MASK_VALUES[part].items()}
        for number, kind in enumerate(GOOD[part]):
            image = f"{part}/Data/Images/Normal/{number:04d}.JPG"
            (root / image).parent.mkdir(parents=True, exist_ok=True)
            _flat(kind).save(root / image, quality=95)
            annotations.append([image, "normal", ""])
            split_rows.append([part, "test", "normal", image, ""])
        for number, (visa_label, kind, placed) in enumerate(boards):
            image = f"{part}/Data/Images/Anomaly/{number:03d}.JPG"
            mask = f"{part}/Data/Masks/Anomaly/{number:03d}.png"
            (root / image).parent.mkdir(parents=True, exist_ok=True)
            (root / mask).parent.mkdir(parents=True, exist_ok=True)
            _flat(kind).save(root / image, quality=95)
            pixels = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
            for visa_type, where in placed.items():
                pixels[where] = values[visa_type]
            Image.fromarray(pixels).save(root / mask)
            annotations.append([image, visa_label, mask])
            split_rows.append([part, "test", "anomaly", image, mask])
        with (root / part / "image_anno.csv").open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, lineterminator="\n").writerows(annotations)
    (root / "split_csv").mkdir(parents=True, exist_ok=True)
    with (root / "split_csv" / "1cls.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(split_rows)


def stub_scorer(part: str) -> StubScorer:
    """Give the stub anomaly model, as the model of a real part.

    Args:
        part: The part it is to score.

    Returns:
        The stub.
    """
    scorer = StubScorer()
    scorer.category = part
    return scorer


def stub_models(part: str) -> LoadedModel:
    """Give the stub as a part's trained model, with a training record to cite.

    Args:
        part: The part.

    Returns:
        The stub and what its training is said to have recorded.
    """
    return LoadedModel(
        scorer=stub_scorer(part),
        trained_at="2026-10-10T14:19:33+00:00",
        fit_seconds=720.0,
        train_peak_allocated_bytes=8 * 1024**3,
        release=lambda: RELEASED.append(part),
    )


def stub_scoring(scorer: Scorer, items: Sequence[InferenceItem], directory: Path) -> RunIndex:
    """Score with the real inference writer, in this process.

    Args:
        scorer: The model.
        items: The images.
        directory: The run's directory.

    Returns:
        The run's index.
    """
    return run_inference(scorer, items, directory, options=InferenceOptions(num_workers=0))


def write_bench_labels(visa: Path, runs: Path, path: Path) -> None:
    """Derive the fake set's labels as the real ones are: from the data and a test run.

    Args:
        visa: The dataset `write_bench_visa` wrote.
        runs: Where the stub's test runs are written.
        path: The labelled set's file.
    """
    labels: list[ClauseLabel] = []
    for part in BOARDS:
        items = [item for item in visa_test_items(visa, part) if item.label == "bad"]
        stub_scoring(stub_scorer(part), items, runs / part / "test")
        truth = read_region_truth(runs / part / "test", [item.image_id for item in items])
        labels.extend(derive_labels(visa, part, truth))
    write_labels(path, labels)


def fake_probes(*, up: bool = True) -> Probes:
    """Give probes of a machine with a card, a server process and its command line.

    Args:
        up: Whether the judge's server answers.

    Returns:
        The probes.
    """
    return Probes(
        read_gpu=lambda pid: GpuReading(
            gpu_used_mib=10000, server_mib=8700 if pid == 4242 else 1300
        ),
        own_pid=lambda: 1,
        server_pid=lambda _url: 4242,
        server_facts=lambda _url: {"model_file": "fake-q4.gguf"},
        server_arguments=lambda _pid: ("llama-server", "--image-min-tokens", "1024"),
        reachable=lambda _url: up,
        gpu_name=lambda: "Fake GPU",
        interval_seconds=0.01,
    )
