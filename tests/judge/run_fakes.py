"""A run directory as the anomaly model writes it, built with a stub scorer for the judge's tests.

The images are flat colours 1000 by 800 pixels; the stub reads a board's kind
from its red level and answers with a fixed score and anomaly map, and the
real `run_inference` writes the sidecars, masks, label images and crops. With
the fake specification of `tests.spec.spec_fakes` (part `pcb9`, 50 mm across
the image, zone A the middle half, zone B the whole frame) a pixel is 0.05 mm.
"""

from pathlib import Path
from typing import Final, Literal

import numpy as np
import torch
from PIL import Image
from torchvision.transforms.v2 import Resize  # pyright: ignore[reportMissingTypeStubs]

from spec_to_inspector.anomaly.infer import InferenceItem, run_inference
from spec_to_inspector.anomaly.records import InferenceOptions, RunIndex, Thresholds

WIDTH: Final = 1000
HEIGHT: Final = 800
CATEGORY: Final = "pcb9"

Kind = Literal["good", "speck", "scratch", "two", "peak"]

_RED: Final[dict[Kind, int]] = {"good": 20, "speck": 90, "scratch": 140, "two": 190, "peak": 240}


def _thresholds() -> Thresholds:
    return Thresholds(
        image=30.0,
        pixel=25.0,
        image_min=5.0,
        image_max=60.0,
        pixel_min=1.0,
        pixel_max=60.0,
        method="test",
        val_split_mode="same_as_test",
        split_images=4,
        split_images_in_test=4,
        tuned_on_test=True,
    )


def _map(kind: Kind) -> tuple[float, torch.Tensor]:
    """Give a board kind's image score and its 256 by 256 anomaly map."""
    anomaly_map = torch.full((256, 256), 5.0)
    if kind == "good":
        return 10.0, anomaly_map
    if kind == "speck":  # a few pixels in the top right corner: zone B only, under 1 mm
        anomaly_map[10:12, 230:232] = 45.0
        return 45.0, anomaly_map
    if kind == "scratch":  # a long bar through the middle: zone A, far over 0.5 mm
        anomaly_map[120:126, 100:150] = 50.0
        return 50.0, anomaly_map
    if kind == "two":  # the speck, hotter, and the bar: region 1 is the speck
        anomaly_map[10:12, 230:232] = 55.0
        anomaly_map[120:126, 100:150] = 50.0
        return 55.0, anomaly_map
    anomaly_map[128, 128] = 20.0  # flagged, with nothing above the threshold: a peak patch
    return 40.0, anomaly_map


class StubScorer:
    """A scorer that knows each board by its red level."""

    category = CATEGORY
    thresholds = _thresholds()
    resize = Resize((256, 256), antialias=True)
    map_cell = (8, 8)

    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Score a batch of resized images.

        Args:
            images: The batch, as (B, 3, 256, 256) in 0 to 1.

        Returns:
            The image scores and the anomaly maps.
        """
        scores: list[float] = []
        maps: list[torch.Tensor] = []
        for image in images:
            red = float(image[0].mean()) * 255
            kind = min(_RED, key=lambda name: abs(_RED[name] - red))
            score, anomaly_map = _map(kind)
            scores.append(score)
            maps.append(anomaly_map)
        return torch.tensor(scores), torch.stack(maps)


def write_run(root: Path, boards: dict[str, Kind], *, max_crops: int | None = None) -> Path:
    """Write a run of flat-colour boards through the real inference writer.

    Args:
        root: A temporary directory.
        boards: Each image id and the kind of board it shows, in run order.
        max_crops: The run's crop limit, if any.

    Returns:
        The run's directory, holding `run.json` and one directory per image.
    """
    items: list[InferenceItem] = []
    for image_id, kind in boards.items():
        path = root / "source" / f"{image_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        colour = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        colour[..., 0] = _RED[kind]
        colour[..., 1] = 110
        Image.fromarray(colour).save(path)
        items.append(InferenceItem(image_id=image_id, path=path))
    output = root / "runs" / CATEGORY / "batch"
    index: RunIndex = run_inference(
        StubScorer(), items, output, options=InferenceOptions(num_workers=0, max_crops=max_crops)
    )
    assert [entry.image_id for entry in index.entries] == list(boards)
    return output
