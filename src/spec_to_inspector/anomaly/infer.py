"""Score images with a trained PatchCore and write what the later stages read.

A run is one directory, built whole and renamed into place:

    <runs_dir>/<category>/<batch>/
        run.json                      the `RunIndex`: thresholds, options, one line per image
        <image_id>/
            result.json               the `ImageResult` sidecar
            anomaly_map.npy           float32 (256, 256): raw PatchCore distances at the
                                      model's resolution
            mask.png                  8-bit, the source image's size: 0 or 255
            regions.png               16-bit, the source image's size: 0 for background,
                                      k for the pixels of region k
            crops/region-001.png ...  the source image's own pixels around each region

The batch is "test" for a category's VisA test split, whose image ids are
"good-<stem>" and "bad-<stem>".

**How a mask maps back to the source image.** The model sees the image
resized to 256 x 256 without keeping its aspect ratio, so the stored map's
pixel (u, v) covers the source rectangle of width W/256 and height H/256 at
(u * W/256, v * H/256). The mask, the label image and every box in the
sidecar are already in source pixels: the map is stretched to (H, W)
bilinearly (`regions.upsample`) and thresholded there, so pixel (x, y) of
`mask.png` is pixel (x, y) of the source image as PIL decodes it (EXIF
orientation not applied, as in Anomalib's own reader).
"""

import math
import re
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, Protocol, Self, cast

import cv2
import numpy as np
import torch
from anomalib.data.utils import read_image
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel, ConfigDict, field_validator
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms.v2 import (  # pyright: ignore[reportMissingTypeStubs]
    Resize,
    Transform,
)

from spec_to_inspector.anomaly.atomic import atomic_directory
from spec_to_inspector.anomaly.metrics import auroc
from spec_to_inspector.anomaly.model import SingleCopyPatchcore
from spec_to_inspector.anomaly.records import (
    ImageResult,
    InferenceOptions,
    Region,
    RunEntry,
    RunIndex,
    Thresholds,
    TrainRecord,
)
from spec_to_inspector.anomaly.regions import crop_box, find_regions, peak_patch, upsample
from spec_to_inspector.anomaly.split import split_images
from spec_to_inspector.anomaly.train import CHECKPOINT_NAME, load_train_record, model_dir

RESULT_NAME: Final = "result.json"
RUN_INDEX_NAME: Final = "run.json"
MAP_NAME: Final = "anomaly_map.npy"
MASK_NAME: Final = "mask.png"
REGIONS_NAME: Final = "regions.png"
CROPS_DIR: Final = "crops"
TEST_BATCH: Final = "test"

_IMAGE_ID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class InferenceItem(BaseModel):
    """One image to score.

    Attributes:
        image_id: The image's name within its run and its output directory's
            name: letters, digits, dots, dashes and underscores.
        path: The image file.
        label: The ground truth, where it is known.
        mask_path: The ground-truth mask, where there is one: 8-bit, 0 for background
            and non-zero on a defect.
        visa_image: The image's path in VisA's CSVs, where it is VisA's.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    path: Path
    label: Literal["good", "bad"] | None = None
    mask_path: Path | None = None
    visa_image: str | None = None

    @field_validator("image_id")
    @classmethod
    def _plain(cls, value: str) -> str:
        """Refuse an id that could not name a directory inside the run.

        Args:
            value: The proposed id.

        Returns:
            The id unchanged.

        Raises:
            ValueError: If the id holds a separator, starts with a dot, or is
                the run index's own file name.
        """
        if not _IMAGE_ID.fullmatch(value):
            msg = f"image_id must be letters, digits, '.', '-' or '_', got {value!r}"
            raise ValueError(msg)
        if value == RUN_INDEX_NAME:
            msg = f"image_id {value!r} is reserved for the run's index"
            raise ValueError(msg)
        return value


class Scorer(Protocol):
    """What a run needs of a model: its category, its thresholds, its resize and its scores."""

    @property
    def category(self) -> str:
        """The category the model was trained on."""
        ...

    @property
    def thresholds(self) -> Thresholds:
        """The thresholds to apply, in raw units."""
        ...

    @property
    def resize(self) -> Transform:
        """The resize applied to each decoded image before it is batched."""
        ...

    @property
    def map_cell(self) -> tuple[int, int]:
        """The rows and columns of the anomaly map that one patch covers."""
        ...

    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Score a batch of resized images.

        Args:
            images: Float images in [0, 1], as (batch, 3, height, width).

        Returns:
            The raw image scores as (batch,) and the raw anomaly maps as
            (batch, height, width).
        """
        ...


class AnomalyModel:
    """A trained PatchCore with its thresholds, ready to score images on a device."""

    def __init__(
        self, module: SingleCopyPatchcore, record: TrainRecord, device: torch.device
    ) -> None:
        """Bind a loaded module to its training record.

        Args:
            module: The module, in evaluation mode on `device`.
            record: The record written when the module was trained.
            device: Where the module lives.

        Raises:
            ValueError: If the module has no resize or no transform to apply.
        """
        pre_processor = module.pre_processor
        transform = (
            None if pre_processor is None else cast("Transform | None", pre_processor.transform)
        )
        resizes = [] if transform is None else _resizes(transform)
        if transform is None or not resizes:
            msg = f"the {record.category} model's pre-processor has no resize to apply"
            raise ValueError(msg)
        self._module = module
        self._record = record
        self._device = device
        self._transform = transform
        self._resize = resizes[0]

    @classmethod
    def load(cls, models_dir: Path, category: str, *, device: str = "cuda") -> Self:
        """Load a category's trained model.

        Args:
            models_dir: The root for trained models.
            category: The category's name.
            device: The device to score on.

        Returns:
            The model, ready to score.

        Raises:
            ModelNotTrainedError: If the model or its record is not on disk.
            ValueError: If the checkpoint's thresholds are not the record's.
        """
        record = load_train_record(models_dir, category)
        checkpoint = model_dir(models_dir, category) / CHECKPOINT_NAME
        target = torch.device(device)
        module = SingleCopyPatchcore.load_from_checkpoint(checkpoint, map_location=target)
        post_processor = module.post_processor
        if not isinstance(module, SingleCopyPatchcore) or post_processor is None:
            msg = f"{checkpoint} is not a PatchCore checkpoint with its post-processor"
            raise ValueError(msg)
        module.eval()
        stored = (
            float(cast("torch.Tensor", post_processor.image_threshold).item()),
            float(cast("torch.Tensor", post_processor.pixel_threshold).item()),
        )
        if stored != (record.thresholds.image, record.thresholds.pixel):
            msg = (
                f"{checkpoint} holds the thresholds {stored}, but its record says "
                f"{(record.thresholds.image, record.thresholds.pixel)}: train the category again"
            )
            raise ValueError(msg)
        return cls(module, record, target)

    @property
    def category(self) -> str:
        """The category the model was trained on."""
        return self._record.category

    @property
    def record(self) -> TrainRecord:
        """The record written when the model was trained."""
        return self._record

    @property
    def thresholds(self) -> Thresholds:
        """The thresholds chosen at training, in raw units."""
        return self._record.thresholds

    @property
    def resize(self) -> Transform:
        """The model's own resize, applied to each decoded image before it is batched."""
        return self._resize

    @property
    def map_cell(self) -> tuple[int, int]:
        """The rows and columns of the anomaly map that one patch covers.

        The backbone's first extracted layer sets the patch grid: 32 x 32 for a
        256 x 256 input, so a patch covers 8 x 8 pixels of the map.
        """
        height, width = self._record.model.image_size
        grid = math.isqrt(self._record.embedding_rows // self._record.train_images)
        return height // grid, width // grid

    @property
    def device(self) -> torch.device:
        """Where the model lives."""
        return self._device

    @property
    def resident_bytes(self) -> int:
        """Bytes of the model's parameters and buffers: the backbone and the memory bank."""
        tensors = [*self._module.parameters(), *self._module.buffers()]
        return sum(tensor.numel() * tensor.element_size() for tensor in tensors)

    @torch.inference_mode()
    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Score a batch of resized images.

        The batch goes through the model's own transform (its resize, which
        changes nothing at this size, and its normalisation) and the PatchCore
        network, as Anomalib's prediction loop does; nothing is normalised or
        thresholded here.

        Args:
            images: Float images in [0, 1], as (batch, 3, height, width).

        Returns:
            The raw image scores as (batch,) and the raw anomaly maps as
            (batch, height, width), on the model's device.
        """
        batch = cast("torch.Tensor", self._transform(images.to(self._device)))
        output = self._module.model(batch)
        return output.pred_score.reshape(-1), output.anomaly_map.squeeze(1)


def _resizes(transform: Transform) -> list[Resize]:
    """Find the resizes in a transform, as Anomalib does for its datasets."""
    if isinstance(transform, Resize):
        return [transform]
    children = cast("Sequence[Transform]", getattr(transform, "transforms", ()))
    return [found for child in children for found in _resizes(child)]


class _Images(Dataset[tuple[torch.Tensor, int]]):
    """Decodes and resizes images as Anomalib's datasets do, keeping each one's position."""

    def __init__(self, paths: Sequence[Path], resize: Transform) -> None:
        self._paths = list(paths)
        self._resize = resize

    def __len__(self) -> int:
        return len(self._paths)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        image = cast("torch.Tensor", read_image(self._paths[index], as_tensor=True))
        return cast("torch.Tensor", self._resize(image)), index


def image_dataset(paths: Sequence[Path], resize: Transform) -> Dataset[tuple[torch.Tensor, int]]:
    """A dataset that decodes and resizes images as Anomalib's own datasets do.

    Args:
        paths: The image files.
        resize: The resize to apply to each decoded image.

    Returns:
        A dataset of (resized float image in [0, 1], position in `paths`).
    """
    return _Images(paths, resize)


def run_dir(runs_dir: Path, category: str, batch: str = TEST_BATCH) -> Path:
    """Where a run's outputs live.

    Args:
        runs_dir: The root for run outputs.
        category: The category whose model scored the images.
        batch: The run's name; "test" for the category's VisA test split.

    Returns:
        The run's directory.
    """
    return runs_dir / category / batch


def visa_test_items(visa_dir: Path, category: str) -> list[InferenceItem]:
    """List a category's VisA test split as inference items.

    Args:
        visa_dir: The dataset directory `data fetch` wrote.
        category: The category's name.

    Returns:
        The test images in the CSV's order, with ids "good-<stem>" and
        "bad-<stem>", their labels, their VisA paths, and VisA's own masks,
        whose values are defect types.
    """
    return [
        InferenceItem(
            image_id=f"{image.label}-{image.path.stem}",
            path=image.path,
            label=image.label,
            mask_path=image.visa_mask,
            visa_image=image.visa_image,
        )
        for image in split_images(visa_dir, category, "test")
    ]


def write_image_result(
    item: InferenceItem,
    *,
    category: str,
    score: float,
    anomaly_map: NDArray[np.float32],
    thresholds: Thresholds,
    directory: Path,
    options: InferenceOptions,
    map_cell: tuple[int, int],
) -> ImageResult:
    """Write one image's map, mask, label image, crops and sidecar.

    Args:
        item: The image scored.
        category: The category whose model scored it.
        score: The raw image score.
        anomaly_map: The raw anomaly map at the model's resolution, as (rows, columns).
        thresholds: The thresholds to apply.
        directory: The image's output directory, which exists.
        options: The crop and region settings.
        map_cell: The rows and columns of the map that one patch covers.

    Returns:
        The sidecar, as written to `result.json`.

    Raises:
        ValueError: If the item's ground-truth mask is unreadable or not the image's size.
    """
    with Image.open(item.path) as opened:
        source = np.asarray(opened.convert("RGB"))
    height, width = source.shape[:2]
    flagged = score > thresholds.image
    region_threshold = thresholds.image if options.region_threshold == "image" else thresholds.pixel

    scores = upsample(anomaly_map, width=width, height=height)
    labels, found = find_regions(
        scores, threshold=region_threshold, min_area=options.min_region_area
    )
    if flagged and not found and options.peak_fallback:
        labels, patch = peak_patch(anomaly_map, scores, map_cell=map_cell)
        found = [patch]
    truth = None if item.mask_path is None else _ground_truth(item.mask_path, (height, width))
    mask = np.where(labels > 0, 255, 0).astype(np.uint8)
    np.save(directory / MAP_NAME, anomaly_map)
    _write_png(directory / MASK_NAME, mask)
    _write_png(directory / REGIONS_NAME, labels)

    regions: list[Region] = []
    for located in found:
        region = located
        if truth is not None:
            under = np.unique(truth[labels == region.index])
            values = [int(value) for value in under if value]
            region = region.model_copy(
                update={"on_ground_truth": bool(values), "ground_truth_values": values}
            )
        if options.max_crops is not None and region.index > options.max_crops:
            regions.append(region)
            continue
        box = crop_box(
            region.bbox,
            width=width,
            height=height,
            margin=options.crop_margin,
            min_side=options.crop_min_side,
        )
        name = f"{CROPS_DIR}/region-{region.index:03d}.png"
        (directory / CROPS_DIR).mkdir(exist_ok=True)
        crop = source[box.y : box.y + box.height, box.x : box.x + box.width]
        Image.fromarray(crop).save(directory / name)
        regions.append(region.model_copy(update={"crop": name, "crop_box": box}))

    result = ImageResult(
        category=category,
        image_id=item.image_id,
        image=str(item.path),
        visa_image=item.visa_image,
        width=width,
        height=height,
        label=item.label,
        ground_truth_mask=None if item.mask_path is None else str(item.mask_path),
        score=score,
        image_threshold=thresholds.image,
        score_normalised=thresholds.normalise_image(score),
        predicted_anomalous=flagged,
        pixel_threshold=thresholds.pixel,
        region_threshold=region_threshold,
        region_threshold_source=options.region_threshold,
        map_width=anomaly_map.shape[1],
        map_height=anomaly_map.shape[0],
        map_max=float(anomaly_map.max()),
        anomaly_map=MAP_NAME,
        mask=MASK_NAME,
        mask_pixels=int(np.count_nonzero(mask)),
        regions_image=REGIONS_NAME,
        regions=regions,
    )
    (directory / RESULT_NAME).write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result


def _ground_truth(path: Path, shape: tuple[int, int]) -> NDArray[np.uint8]:
    """Read a ground-truth mask with its values, checking it fits its image."""
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    # OpenCV's stubs promise an array, but an undecodable file yields None.
    if mask is None or mask.shape != shape:  # pyright: ignore[reportUnnecessaryComparison]
        found = "unreadable" if mask is None else f"{mask.shape[1]} x {mask.shape[0]}"  # pyright: ignore[reportUnnecessaryComparison]
        msg = f"the ground-truth mask {path} is {found}, not the image's {shape[1]} x {shape[0]}"
        raise ValueError(msg)
    return cast("NDArray[np.uint8]", mask)


def _write_png(path: Path, image: NDArray[np.uint8] | NDArray[np.uint16]) -> None:
    """Write a single-channel PNG, failing loudly if OpenCV does not."""
    if not cv2.imwrite(str(path), image):
        msg = f"could not write {path}"
        raise OSError(msg)


def run_inference(
    model: Scorer,
    items: Sequence[InferenceItem],
    output_dir: Path,
    *,
    options: InferenceOptions | None = None,
) -> RunIndex:
    """Score a batch of images and write the run's directory.

    The directory is built beside its place and renamed in, replacing any
    earlier run of the same name whole.

    Args:
        model: The trained model.
        items: The images, each with an id unique in the run.
        output_dir: The run's directory, such as `run_dir(runs_dir, category)`.
        options: How to score and crop; the defaults if None.

    Returns:
        The run's index, as written to `run.json`.

    Raises:
        ValueError: If two items share an image id.
    """
    options = options or InferenceOptions()
    seen: set[str] = set()
    for item in items:
        if item.image_id in seen:
            msg = f"two images share the image_id {item.image_id!r}"
            raise ValueError(msg)
        seen.add(item.image_id)

    thresholds = model.thresholds
    results: dict[int, ImageResult] = {}
    started = time.perf_counter()
    with atomic_directory(output_dir) as partial:
        loader = DataLoader(
            _Images([item.path for item in items], model.resize),
            batch_size=options.batch_size,
            num_workers=options.num_workers,
            shuffle=False,
        )
        for images, positions in loader:
            scores, maps = model.score(images)
            host_scores = [float(value) for value in scores.double().cpu()]
            host_maps = cast("NDArray[np.float32]", maps.float().cpu().numpy())
            for row, position in enumerate(int(p) for p in cast("torch.Tensor", positions)):
                item = items[position]
                directory = partial / item.image_id
                directory.mkdir()
                results[position] = write_image_result(
                    item,
                    category=model.category,
                    score=host_scores[row],
                    anomaly_map=np.ascontiguousarray(host_maps[row]),
                    thresholds=thresholds,
                    directory=directory,
                    options=options,
                    map_cell=model.map_cell,
                )

        ordered = [results[position] for position in range(len(items))]
        index = RunIndex(
            category=model.category,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            thresholds=thresholds,
            options=options,
            images=len(ordered),
            labelled_good=sum(result.label == "good" for result in ordered),
            labelled_bad=sum(result.label == "bad" for result in ordered),
            image_auroc=auroc(
                [result.score for result in ordered if result.label is not None],
                [result.label == "bad" for result in ordered if result.label is not None],
            ),
            seconds=time.perf_counter() - started,
            entries=[
                RunEntry(
                    image_id=result.image_id,
                    result=f"{result.image_id}/{RESULT_NAME}",
                    label=result.label,
                    score=result.score,
                    predicted_anomalous=result.predicted_anomalous,
                    regions=len(result.regions),
                    peak_fallback=any(region.from_peak for region in result.regions),
                    top_region_on_ground_truth=(
                        result.regions[0].on_ground_truth if result.regions else None
                    ),
                )
                for result in ordered
            ],
        )
        (partial / RUN_INDEX_NAME).write_text(
            index.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return index


def load_run_index(directory: Path) -> RunIndex:
    """Read a run's index.

    Args:
        directory: The run's directory.

    Returns:
        The index.
    """
    return RunIndex.model_validate_json((directory / RUN_INDEX_NAME).read_text(encoding="utf-8"))


def load_result(directory: Path) -> ImageResult:
    """Read one image's sidecar.

    Args:
        directory: The image's output directory.

    Returns:
        The sidecar.
    """
    return ImageResult.model_validate_json((directory / RESULT_NAME).read_text(encoding="utf-8"))


def load_anomaly_map(
    directory: Path, result: ImageResult, *, at_source: bool = False
) -> NDArray[np.float32]:
    """Read one image's raw anomaly map.

    Args:
        directory: The image's output directory.
        result: The image's sidecar.
        at_source: Whether to stretch the map to the source image's size, as
            was done before it was thresholded into the mask.

    Returns:
        The map as (map_height, map_width), or as (height, width) if stretched.
    """
    anomaly_map = cast("NDArray[np.float32]", np.load(directory / result.anomaly_map))
    if at_source:
        return upsample(anomaly_map, width=result.width, height=result.height)
    return anomaly_map
