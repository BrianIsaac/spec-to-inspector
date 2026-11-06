"""PatchCore through OpenVINO: the export of a trained model, and a scorer for what comes out.

OpenVINO is only in the `xpu` group, so nothing here imports it until it is asked for.

Four things about the export are not what its defaults give:

- **Raw units.** Anomalib's export runs through its post-processor, which normalises and clips the
  score and the map. Everything downstream, the thresholds included, works in raw PatchCore
  distances, so normalising and thresholding are switched off in the copy that is exported.
- **One batch size to a graph.** Anomalib asks for a dynamic batch, but PatchCore's nearest-
  neighbour search is a Python loop over chunks of 1,024 patches, and the exporter fixes the batch
  at its example's: 2, an input of `[2, 3, 256, 256]` (measured). So a graph is exported for each
  batch size, by naming the size, and each compiled graph is the same chunked search PyTorch runs.
- **The opset.** Anomalib's default of 14 sends the exporter's opset-18 graph through a downgrade
  that fails on this model and prints a traceback. 18 needs no downgrade.
- **FP32.** The GPU plugin's default is to infer in FP16 even with FP32 weights (measured: its
  `INFERENCE_PRECISION_HINT` reads `f16` unasked). FP32 is asked for, read back and enforced, and
  a graph with FP16 weights is refused.
"""

import time
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any, Final, Self, cast

import numpy as np
import torch
from numpy.typing import NDArray
from torchvision.transforms.v2 import (  # pyright: ignore[reportMissingTypeStubs]
    Resize,
    Transform,
)

from spec_to_inspector.anomaly.infer import patch_cell
from spec_to_inspector.anomaly.model import SingleCopyPatchcore
from spec_to_inspector.anomaly.records import Thresholds, TrainRecord
from spec_to_inspector.anomaly.train import (
    CHECKPOINT_NAME,
    IMAGE_SIZE,
    load_train_record,
    model_dir,
)

OPENVINO_DEVICE: Final = "GPU.0"
"""The card, as OpenVINO names it. Under `ZE_AFFINITY_MASK=0` it lists only `GPU`."""
EXPORT_OPSET: Final = 18
IR_NAME: Final = "model"
FP32_HINT: Final = "f32"
_SCORE_OUTPUT: Final = "pred_score"
_MAP_OUTPUT: Final = "anomaly_map"


def _openvino() -> Any:  # noqa: ANN401 - the package is absent where pyright runs, on the laptop
    """Import OpenVINO, which only the `xpu` group installs.

    Returns:
        The module.

    Raises:
        RuntimeError: If it is not installed.
    """
    try:
        return import_module("openvino")
    except ModuleNotFoundError as error:
        msg = "OpenVINO is not installed: it is in the xpu group, see scripts/setup_xpu.sh"
        raise RuntimeError(msg) from error


def ir_path(models_dir: Path, category: str, batch_size: int) -> Path:
    """Where the exported graph of a category and a batch size lives.

    Args:
        models_dir: The root for trained models.
        category: The category's name.
        batch_size: The batch the graph is fixed at.

    Returns:
        The `.xml` file; its weights are the `.bin` beside it.
    """
    root = model_dir(models_dir, category) / "openvino" / f"batch-{batch_size}"
    return root / "weights" / "openvino" / f"{IR_NAME}.xml"


def export_openvino(models_dir: Path, category: str, *, batch_size: int) -> Path:
    """Export a category's trained model to OpenVINO, in FP32, at a fixed batch.

    The export runs on the CPU and uses no card. The module's own checkpoint is read and a copy
    is changed, so the trained model on disk is not touched.

    Args:
        models_dir: The root for trained models.
        category: The category's name.
        batch_size: The batch to fix the graph at.

    Returns:
        The graph's `.xml` file.

    Raises:
        ModelNotTrainedError: If the model or its record is not on disk.
        ValueError: If the checkpoint is not a PatchCore checkpoint with its post-processor.
    """
    load_train_record(models_dir, category)
    checkpoint = model_dir(models_dir, category) / CHECKPOINT_NAME
    module = SingleCopyPatchcore.load_from_checkpoint(checkpoint, map_location="cpu")
    post_processor = cast("Any", module.post_processor)
    if not isinstance(module, SingleCopyPatchcore) or post_processor is None:
        msg = f"{checkpoint} is not a PatchCore checkpoint with its post-processor"
        raise ValueError(msg)
    module.eval()
    post_processor.enable_normalization = False
    post_processor.enable_thresholding = False
    target = ir_path(models_dir, category, batch_size)
    return module.to_openvino(
        target.parents[2],
        model_file_name=IR_NAME,
        input_size=IMAGE_SIZE,
        onnx_kwargs={"opset_version": EXPORT_OPSET, "dynamic_shapes": ({0: batch_size},)},
    )


Inference = Callable[[NDArray[np.float32]], tuple[NDArray[np.float32], NDArray[np.float32]]]
"""One compiled graph's request: a full batch in, its raw scores and raw maps out."""


class OpenVinoModel:
    """An exported PatchCore on a card through OpenVINO, ready to score images.

    A graph takes one batch size, so a batch is cut to that size and a short one is filled out by
    repeating its last image, whose answers are dropped. A run of 200 images at batch 16 therefore
    computes 208. An image's answer does not depend on the others: every step works per patch.
    """

    def __init__(
        self,
        infer: Inference,
        record: TrainRecord,
        *,
        batch_size: int,
        resident_bytes: int,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Bind a compiled graph to its training record.

        Args:
            infer: Runs one full batch.
            record: The record written when the model was trained.
            batch_size: The batch the graph is fixed at.
            resident_bytes: The size of the graph's weights.
            properties: What the plugin says it compiled, for the record.
        """
        self._infer = infer
        self._record = record
        self._batch_size = batch_size
        self._resident_bytes = resident_bytes
        self._resize = Resize(IMAGE_SIZE, antialias=True)
        self.properties = properties or {}

    @classmethod
    def load(
        cls,
        models_dir: Path,
        category: str,
        *,
        batch_size: int,
        device: str = OPENVINO_DEVICE,
    ) -> Self:
        """Compile a category's exported graph on a device, in FP32.

        Args:
            models_dir: The root for trained models.
            category: The category's name.
            batch_size: The batch of the graph to load.
            device: The device, as OpenVINO names it.

        Returns:
            The model, ready to score.

        Raises:
            ModelNotTrainedError: If the model or its record is not on disk.
            RuntimeError: If OpenVINO is not installed, or the plugin would not infer in FP32.
            ValueError: If the graph's weights are in FP16.
        """
        record = load_train_record(models_dir, category)
        openvino = _openvino()
        path = ir_path(models_dir, category, batch_size)
        core = openvino.Core()
        graph = core.read_model(path)
        weights = {
            str(operation.get_element_type())
            for operation in graph.get_ordered_ops()
            if operation.get_type_name() == "Constant"
        }
        if any("16" in kind and "float" in kind for kind in weights):
            msg = f"{path} holds FP16 weights ({sorted(weights)}): export it again in FP32"
            raise ValueError(msg)
        compiled = core.compile_model(graph, device, {"INFERENCE_PRECISION_HINT": FP32_HINT})
        precision = str(compiled.get_property("INFERENCE_PRECISION_HINT"))
        if "float32" not in precision and FP32_HINT not in precision:
            msg = f"the {device} plugin asked for FP32 compiled in {precision}"
            raise RuntimeError(msg)
        request = compiled.create_infer_request()
        score_output, map_output = compiled.output(_SCORE_OUTPUT), compiled.output(_MAP_OUTPUT)

        def infer(batch: NDArray[np.float32]) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
            request.infer({0: batch})
            return (
                np.array(request.get_tensor(score_output).data),
                np.array(request.get_tensor(map_output).data),
            )

        properties = {
            "openvino": str(openvino.__version__),
            "device": device,
            "device_name": str(core.get_property(device, "FULL_DEVICE_NAME")),
            "precision": precision,
            "plugin_default_precision": str(
                openvino.Core().get_property(device, "INFERENCE_PRECISION_HINT")
            ),
            "performance_hint": str(compiled.get_property("PERFORMANCE_HINT")),
            "streams": str(compiled.get_property("NUM_STREAMS")),
            "weights_element_types": ", ".join(sorted(weights)),
            "input_shape": str(graph.input(0).get_partial_shape()),
        }
        return cls(
            infer,
            record,
            batch_size=batch_size,
            resident_bytes=path.with_suffix(".bin").stat().st_size,
            properties=properties,
        )

    @property
    def category(self) -> str:
        """The category the model was trained on."""
        return self._record.category

    @property
    def thresholds(self) -> Thresholds:
        """The thresholds chosen at training, in raw units."""
        return self._record.thresholds

    @property
    def resize(self) -> Transform:
        """The resize applied to each decoded image before it is batched, the model's own."""
        return self._resize

    @property
    def map_cell(self) -> tuple[int, int]:
        """The rows and columns of the anomaly map that one patch covers."""
        return patch_cell(self._record)

    @property
    def device(self) -> torch.device:
        """Where PyTorch's side of this model lives: the host, as OpenVINO holds the card."""
        return torch.device("cpu")

    @property
    def resident_bytes(self) -> int:
        """Bytes of the graph's weights: the backbone and the memory bank."""
        return self._resident_bytes

    def score(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Score a batch of resized images.

        Args:
            images: Float images in [0, 1], as (batch, 3, height, width).

        Returns:
            The raw image scores as (batch,) and the raw anomaly maps as (batch, height, width),
            in host memory.
        """
        scores: list[NDArray[np.float32]] = []
        maps: list[NDArray[np.float32]] = []
        pixels = cast("NDArray[np.float32]", images.numpy(force=True))
        for start in range(0, pixels.shape[0], self._batch_size):
            chunk = pixels[start : start + self._batch_size]
            used = chunk.shape[0]
            if used < self._batch_size:
                filler = np.repeat(chunk[-1:], self._batch_size - used, axis=0)
                chunk = np.concatenate([chunk, filler])
            chunk_scores, chunk_maps = self._infer(chunk)
            scores.append(chunk_scores.reshape(-1)[:used])
            maps.append(chunk_maps[:used, 0])
        return torch.as_tensor(np.concatenate(scores)), torch.as_tensor(np.concatenate(maps))

    def first_use(self) -> float:
        """Run the first request on the graph, the one that finishes compiling its kernels.

        Returns:
            How long it took, in seconds.
        """
        started = time.perf_counter()
        self.score(torch.zeros((self._batch_size, 3, *IMAGE_SIZE)))
        return time.perf_counter() - started
