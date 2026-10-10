"""The anomaly model's records: what training and inference write beside their files.

Every model here is frozen and is written as JSON; the files they name are
described where they are written (`spec_to_inspector.anomaly.infer`).
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from spec_to_inspector.device import CudaDevice

SCHEMA_VERSION: Final = 1


class Box(BaseModel):
    """An axis-aligned rectangle in a source image's pixels.

    Attributes:
        x: The left column.
        y: The top row.
        width: Columns covered.
        height: Rows covered.
    """

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class Region(BaseModel):
    """One connected area of the thresholded anomaly map, in the source image's pixels.

    Attributes:
        index: The region's rank by peak score, from 1; also the value of its
            pixels in the label image.
        bbox: The tight bounding box.
        area_px: Pixels in the region.
        centroid: The mean position of its pixels, as (x, y).
        peak_score: The highest raw anomaly-map value inside the region.
        peak_xy: Where that value is, as (x, y).
        mean_score: The mean raw anomaly-map value inside the region.
        from_peak: Whether the region is the fallback for an image flagged anomalous
            with nothing above the region threshold: the one patch holding the
            anomaly map's peak. Its size is the patch's, not a defect's.
        on_ground_truth: Whether any of its pixels lie on the ground-truth mask;
            None where the image has no mask.
        ground_truth_values: The distinct non-zero ground-truth mask values under
            the region, ascending; in VisA's masks each is a defect type
            (`anomaly.ground_truth.defect_types`). None where the image has no mask.
        crop: The crop's file, relative to the sidecar; None if no crop was written.
        crop_box: The rectangle of the source image the crop holds; None with `crop`.
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    bbox: Box
    area_px: int = Field(ge=1)
    centroid: tuple[float, float]
    peak_score: float
    peak_xy: tuple[int, int]
    mean_score: float
    from_peak: bool = False
    on_ground_truth: bool | None = None
    ground_truth_values: list[int] | None = None
    crop: str | None = None
    crop_box: Box | None = None


def normalise(value: float, *, threshold: float, low: float, high: float) -> float:
    """Normalise a raw score as Anomalib's post-processor does.

    The threshold lands on 0.5 and the range seen on the threshold's split
    spans one unit, clamped to [0, 1].

    Args:
        value: The raw score.
        threshold: The raw threshold.
        low: The lowest raw score seen on the threshold's split.
        high: The highest raw score seen on the threshold's split.

    Returns:
        The normalised score.
    """
    span = high - low
    if span == 0:
        return 1.0 if value > threshold else 0.0 if value < threshold else 0.5
    return min(max((value - threshold) / span + 0.5, 0.0), 1.0)


class Thresholds(BaseModel):
    """A category's thresholds in raw PatchCore units, and where they come from.

    Attributes:
        image: An image is anomalous when its score is above this.
        pixel: A pixel is anomalous when its anomaly-map value is above this.
        image_min: The lowest image score on the threshold's split.
        image_max: The highest image score on the threshold's split.
        pixel_min: The lowest anomaly-map value on the threshold's split.
        pixel_max: The highest anomaly-map value on the threshold's split.
        method: What chose the thresholds.
        val_split_mode: Anomalib's validation split mode for the run.
        split_images: Images in the split the thresholds were chosen on.
        split_images_in_test: How many of those are also test images.
        tuned_on_test: Whether the thresholds were chosen on test images, in
            which case no thresholded figure is a held-out one.
    """

    model_config = ConfigDict(frozen=True)

    image: float
    pixel: float
    image_min: float
    image_max: float
    pixel_min: float
    pixel_max: float
    method: str
    val_split_mode: str
    split_images: int
    split_images_in_test: int
    tuned_on_test: bool

    def normalise_image(self, score: float) -> float:
        """Normalise an image score: 0.5 at the image threshold.

        Args:
            score: The raw image score.

        Returns:
            The score in [0, 1].
        """
        return normalise(score, threshold=self.image, low=self.image_min, high=self.image_max)

    def normalise_pixel(self, value: float) -> float:
        """Normalise an anomaly-map value: 0.5 at the pixel threshold.

        Args:
            value: The raw anomaly-map value.

        Returns:
            The value in [0, 1].
        """
        return normalise(value, threshold=self.pixel, low=self.pixel_min, high=self.pixel_max)


class ModelSpec(BaseModel):
    """What was trained.

    Attributes:
        name: The model's name in Anomalib.
        variant: The class that ran it.
        backbone: The feature extractor.
        weights: The pretrained weights, as timm names them.
        layers: The backbone layers whose features are concatenated.
        image_size: The model's input, as (height, width); the image is
            resized to it without keeping its aspect ratio.
        coreset_sampling_ratio: The fraction of patch embeddings kept.
        num_neighbors: Neighbours used to weight the image score.
        precision: The model's floating-point precision.
        seed: The seed given to `lightning.seed_everything`.
        train_batch_size: Images per training batch.
        eval_batch_size: Images per validation and test batch.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    variant: str
    backbone: str
    weights: str
    layers: tuple[str, ...]
    image_size: tuple[int, int]
    coreset_sampling_ratio: float
    num_neighbors: int
    precision: str
    seed: int
    train_batch_size: int
    eval_batch_size: int


class Phase(BaseModel):
    """One phase of a run: how long it took and the most GPU memory it held.

    Attributes:
        seconds: Wall time.
        peak_allocated_bytes: `torch.cuda.max_memory_allocated` over the phase.
        peak_reserved_bytes: `torch.cuda.max_memory_reserved` over the phase.
    """

    model_config = ConfigDict(frozen=True)

    seconds: float
    peak_allocated_bytes: int
    peak_reserved_bytes: int


class Metrics(BaseModel):
    """Anomalib's test metrics for a category.

    AUROC needs no threshold. The F1 scores use the thresholds, so where
    those were chosen on the test images they are not held-out figures.

    Attributes:
        image_auroc: Area under the ROC curve of the image scores.
        pixel_auroc: Area under the ROC curve of the anomaly maps against the masks.
        image_f1: F1 of the thresholded image scores.
        pixel_f1: F1 of the thresholded anomaly maps.
    """

    model_config = ConfigDict(frozen=True)

    image_auroc: float
    pixel_auroc: float
    image_f1: float
    pixel_f1: float


class TrainRecord(BaseModel):
    """One category's training, written beside its checkpoint as `train.json`.

    Attributes:
        schema_version: The version of this record's layout.
        category: The category trained.
        created_at: When training ended, in UTC, ISO 8601.
        model: What was trained.
        train_images: Normal images embedded.
        test_good: Normal test images.
        test_bad: Anomalous test images.
        embedding_rows: Patch embeddings before coreset selection.
        memory_bank_rows: Patch embeddings kept.
        memory_bank_dims: Floats per embedding.
        thresholds: The thresholds and their provenance.
        metrics: Anomalib's test metrics.
        embed: Extracting the training images' features.
        coreset: Stacking the embeddings and selecting the coreset.
        validate_split: Scoring the validation split and choosing the thresholds.
        test: Anomalib's test pass.
        fit_seconds: Wall time of `Engine.fit`: embed, coreset, validate and the
            checkpoint's write.
        peak_allocated_bytes: The highest `peak_allocated_bytes` of the phases.
        peak_reserved_bytes: The highest `peak_reserved_bytes` of the phases.
        gpu_free_bytes_before: Free GPU memory when training started, as CUDA
            reported it; other processes' use shows here.
        device: The GPU and the PyTorch build.
        checkpoint: The checkpoint's file, relative to this record.
        checkpoint_bytes: The checkpoint's size.
        versions: The versions of the libraries that did the work.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    category: str
    created_at: str
    model: ModelSpec
    train_images: int
    test_good: int
    test_bad: int
    embedding_rows: int
    memory_bank_rows: int
    memory_bank_dims: int
    thresholds: Thresholds
    metrics: Metrics
    embed: Phase
    coreset: Phase
    validate_split: Phase
    test: Phase
    fit_seconds: float
    peak_allocated_bytes: int
    peak_reserved_bytes: int
    gpu_free_bytes_before: int
    device: CudaDevice
    checkpoint: str
    checkpoint_bytes: int
    versions: dict[str, str]


class ImageResult(BaseModel):
    """One image's inference, written beside its files as `result.json`.

    Every size and position is in the source image's own pixels unless it
    says otherwise; file names are relative to the sidecar's directory.

    Attributes:
        schema_version: The version of this record's layout.
        category: The category whose model scored the image.
        image_id: The image's name within its run; also its directory's name.
        image: The source image's path, as inference was given it.
        visa_image: The image's path in VisA's CSVs, the key into
            `image_anno.csv`; None for an image that is not VisA's.
        width: The source image's width.
        height: The source image's height.
        label: The ground truth, "good" or "bad", where it is known.
        ground_truth_mask: The ground-truth mask's path, where there is one: 0 for
            background, non-zero on a defect. For VisA it is the fetched mask,
            whose values are defect types.
        score: The raw PatchCore image score.
        image_threshold: The raw score above which an image is anomalous.
        score_normalised: The score as Anomalib normalises it: 0.5 at the threshold.
        predicted_anomalous: Whether the score is above the image threshold.
        pixel_threshold: Anomalib's pixel threshold, the raw anomaly-map value its own
            masks are cut at; recorded whether or not it is the one applied.
        region_threshold: The raw anomaly-map value the mask and regions were cut at.
        region_threshold_source: Which threshold that is: "image" or "pixel".
        map_width: The stored anomaly map's width, the model's input width.
        map_height: The stored anomaly map's height, the model's input height.
        map_max: The highest raw value in the anomaly map.
        anomaly_map: The raw anomaly map, a float32 `.npy` of (map_height, map_width).
        mask: The thresholded mask at the source's size: an 8-bit PNG of 0 and 255,
            the union of the regions (so it includes a peak-patch fallback region).
        mask_pixels: Anomalous pixels in the mask.
        regions_image: The label image at the source's size: a 16-bit PNG, 0 for
            background and a region's index for its pixels.
        regions: The connected regions, ranked by peak score.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    category: str
    image_id: str
    image: str
    visa_image: str | None
    width: int
    height: int
    label: Literal["good", "bad"] | None
    ground_truth_mask: str | None
    score: float
    image_threshold: float
    score_normalised: float
    predicted_anomalous: bool
    pixel_threshold: float
    region_threshold: float
    region_threshold_source: Literal["image", "pixel"]
    map_width: int
    map_height: int
    map_max: float
    anomaly_map: str
    mask: str
    mask_pixels: int
    regions_image: str
    regions: list[Region]


class RunEntry(BaseModel):
    """One image's line in a run's index.

    Attributes:
        image_id: The image's name within the run.
        result: The image's sidecar, relative to the index.
        label: The ground truth, where it is known.
        score: The raw image score.
        predicted_anomalous: Whether the score is above the image threshold.
        regions: How many regions the image has.
        peak_fallback: Whether its one region is the peak-patch fallback.
        top_region_on_ground_truth: Whether region 1 touches the ground-truth mask;
            None where the image has no mask or no region.
    """

    model_config = ConfigDict(frozen=True)

    image_id: str
    result: str
    label: Literal["good", "bad"] | None
    score: float
    predicted_anomalous: bool
    regions: int
    peak_fallback: bool
    top_region_on_ground_truth: bool | None


class InferenceOptions(BaseModel):
    """How a run scores its images and cuts its crops.

    Attributes:
        batch_size: Images per forward pass.
        num_workers: Data loader workers decoding and resizing images.
        crop_margin: The margin around a region's box, as a fraction of its longer side.
        crop_min_side: The least width and height of a crop, in source pixels.
        min_region_area: Regions of fewer source pixels are left out.
        max_crops: At most this many crops per image, taken in rank order; None for all.
        region_threshold: Which threshold cuts the anomaly map into regions. "image"
            uses the image threshold, so one level decides both whether a board is
            anomalous and where; "pixel" uses Anomalib's pixel threshold.
        peak_fallback: Whether an image flagged anomalous with nothing above the
            region threshold gets the patch of the map's peak as its region.
    """

    model_config = ConfigDict(frozen=True)

    batch_size: int = Field(default=16, ge=1)
    num_workers: int = Field(default=4, ge=0)
    crop_margin: float = Field(default=0.5, ge=0)
    crop_min_side: int = Field(default=256, ge=1)
    min_region_area: int = Field(default=1, ge=1)
    max_crops: int | None = Field(default=None, ge=0)
    region_threshold: Literal["image", "pixel"] = "image"
    peak_fallback: bool = True


class RunIndex(BaseModel):
    """A run's manifest, written as `run.json` at the top of its directory.

    Attributes:
        schema_version: The version of this record's layout.
        category: The category whose model scored the images.
        created_at: When the run ended, in UTC, ISO 8601.
        thresholds: The thresholds applied, with their provenance.
        options: How the images were scored and cropped.
        images: Images in the run.
        labelled_good: Images whose ground truth is "good".
        labelled_bad: Images whose ground truth is "bad".
        image_auroc: Area under the ROC curve of the raw image scores, where the
            run holds both labels; None otherwise.
        seconds: Wall time of the run, from the first image read to the last file written.
        entries: One line per image, in the order given.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    category: str
    created_at: str
    thresholds: Thresholds
    options: InferenceOptions
    images: int
    labelled_good: int
    labelled_bad: int
    image_auroc: float | None
    seconds: float
    entries: list[RunEntry]


class Throughput(BaseModel):
    """Inference speed at one batch size, by one way of counting.

    Attributes:
        mode: "model" times the forward pass alone, on resized images already on
            the GPU: normalisation, backbone, nearest-neighbour search, anomaly
            map. "end_to_end" starts from the image files: decoding, resizing,
            the copy to the GPU, the forward pass, and the scores and maps
            copied back to host memory; no output files are written.
        batch_size: Images per forward pass.
        images: Images in one pass over the set.
        pass_seconds: Wall time of each pass over the set.
        seconds: The median of `pass_seconds`.
        images_per_second: `images` over `seconds`.
        peak_allocated_bytes: `torch.cuda.max_memory_allocated` over the passes,
            the resident model included.
        peak_reserved_bytes: `torch.cuda.max_memory_reserved` over the passes.
        num_workers: Data loader workers decoding images; None for "model".
    """

    model_config = ConfigDict(frozen=True)

    mode: Literal["model", "end_to_end"]
    batch_size: int
    images: int
    pass_seconds: list[float]
    seconds: float
    images_per_second: float
    peak_allocated_bytes: int
    peak_reserved_bytes: int
    num_workers: int | None


class InferenceBench(BaseModel):
    """A category's inference throughput and memory, written as `bench.json`.

    Attributes:
        schema_version: The version of this record's layout.
        category: The category whose model was measured.
        created_at: When the measurement ended, in UTC, ISO 8601.
        device: The GPU and the PyTorch build.
        images: Images in the set measured, the category's test split.
        resident_bytes: Bytes of the model's parameters and buffers on the device:
            the backbone and the memory bank, what stays on the card between images.
        runs: The figures, per batch size and mode.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    category: str
    created_at: str
    device: CudaDevice
    images: int
    resident_bytes: int
    runs: list[Throughput]
