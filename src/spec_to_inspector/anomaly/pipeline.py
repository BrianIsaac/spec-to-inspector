"""One category from fetched data to scored test split: what `spec-to-inspector train` runs."""

import gc
from pathlib import Path

import torch
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.anomaly.infer import AnomalyModel, run_dir, run_inference, visa_test_items
from spec_to_inspector.anomaly.records import InferenceOptions, RunIndex, TrainRecord
from spec_to_inspector.anomaly.train import (
    DEFAULT_SEED,
    ModelNotTrainedError,
    load_train_record,
    train_category,
)


class CategoryOutcome(BaseModel):
    """What one category's pass through the pipeline produced.

    Attributes:
        category: The category's name.
        trained: Whether the model was trained in this pass; false when one on
            disk was reused.
        record: The model's training record.
        run: The index of the test split's run; None if inference was left out.
        run_dir: The run's directory; None with `run`.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    trained: bool
    record: TrainRecord
    run: RunIndex | None
    run_dir: Path | None


def _release_gpu() -> None:
    """Return freed GPU memory to the driver, so the next category's peak starts clean."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def train_and_score(
    category: str,
    *,
    visa_dir: Path,
    models_dir: Path,
    runs_dir: Path,
    reuse: bool = False,
    infer: bool = True,
    seed: int = DEFAULT_SEED,
    options: InferenceOptions | None = None,
) -> CategoryOutcome:
    """Train a category's model, or reuse the one on disk, and score its test split.

    Args:
        category: The category, such as "pcb4".
        visa_dir: The dataset directory `data fetch` wrote.
        models_dir: The root for trained models.
        runs_dir: The root for run outputs.
        reuse: Whether to keep a model already on disk instead of training again.
        infer: Whether to score the test split into `run_dir(runs_dir, category)`.
        seed: The training seed.
        options: How to score and crop; the defaults if None.

    Returns:
        The category's record and, if scored, its run.

    Raises:
        RuntimeError: If CUDA is not available.
        SplitError: If the split cannot be written from the fetched tree.
    """
    record: TrainRecord | None = None
    if reuse:
        try:
            record = load_train_record(models_dir, category)
        except ModelNotTrainedError:
            record = None
    trained = record is None
    if record is None:
        record = train_category(category, visa_dir=visa_dir, models_dir=models_dir, seed=seed)
        _release_gpu()

    run: RunIndex | None = None
    output: Path | None = None
    if infer:
        output = run_dir(runs_dir, category)
        model = AnomalyModel.load(models_dir, category)
        run = run_inference(
            model,
            visa_test_items(visa_dir, category),
            output,
            options=options or InferenceOptions(),
        )
        del model
        _release_gpu()
    return CategoryOutcome(
        category=category, trained=trained, record=record, run=run, run_dir=output
    )
