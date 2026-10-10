"""Tests for the PatchCore variant that holds its training embeddings once."""

import inspect

import pytest
import torch
from anomalib.data import ImageBatch
from anomalib.models import Patchcore
from lightning.pytorch import seed_everything
from torchvision.tv_tensors import Image

from spec_to_inspector.anomaly.model import SingleCopyPatchcore


def _fit(model: Patchcore, batches: list[torch.Tensor]) -> torch.Tensor:
    """Run the training steps and the coreset selection of a PatchCore on the CPU.

    Returns:
        The memory bank after coreset selection.
    """
    model.train()
    for images in batches:
        model.training_step(ImageBatch(image=Image(images.clone())))
    seed_everything(3)
    model.fit()
    return model.model.memory_bank


def _models() -> tuple[Patchcore, SingleCopyPatchcore]:
    """Build stock PatchCore and the variant with the same weights, on a small backbone.

    Returns:
        Stock Anomalib's model and ours.
    """
    seed_everything(1)
    stock = Patchcore(backbone="resnet18", pre_trained=False, visualizer=False)
    seed_everything(1)
    ours = SingleCopyPatchcore(backbone="resnet18", pre_trained=False, visualizer=False)
    return stock, ours


def _batches() -> list[torch.Tensor]:
    seed_everything(2)
    return [torch.rand(2, 3, 64, 64) for _ in range(3)]


def test_the_memory_bank_equals_stock_anomalibs() -> None:
    """Collecting into one preallocated tensor changes where embeddings sit, not the coreset."""
    stock, ours = _models()
    ours.expected_images = 6
    batches = _batches()

    expected = _fit(stock, batches)
    bank = _fit(ours, batches)

    assert bank.shape == (38, 384)
    assert torch.equal(bank, expected)
    assert ours.embedding_rows == 384


def test_embeddings_go_straight_into_one_tensor_and_are_released() -> None:
    """Each batch's embeddings are written into the one buffer; no list of them is kept."""
    _, ours = _models()
    ours.expected_images = 4
    ours.train()

    ours.training_step(ImageBatch(image=Image(torch.rand(2, 3, 64, 64))))

    assert ours.model.embedding_store == []
    assert ours.buffered_rows == 128
    assert ours.buffer_capacity == 256
    assert ours.embedding_rows == 0

    ours.training_step(ImageBatch(image=Image(torch.rand(2, 3, 64, 64))))
    seed_everything(3)
    ours.fit()

    assert ours.buffer_capacity == 0
    assert ours.embedding_rows == 256
    assert ours.coreset_seconds > 0
    assert ours.model.memory_bank.shape == (25, 384)


def test_fewer_images_than_expected_use_only_what_arrived() -> None:
    """A short epoch selects the coreset from the rows that were filled, not the whole buffer."""
    stock, ours = _models()
    ours.expected_images = 10
    batches = _batches()

    expected = _fit(stock, batches)
    bank = _fit(ours, batches)

    assert ours.embedding_rows == 384
    assert torch.equal(bank, expected)


def test_more_images_than_expected_is_an_error() -> None:
    """An epoch larger than the buffer is refused rather than silently truncated."""
    _, ours = _models()
    ours.expected_images = 2
    ours.train()
    ours.training_step(ImageBatch(image=Image(torch.rand(2, 3, 64, 64))))

    with pytest.raises(ValueError, match="expected_images"):
        ours.training_step(ImageBatch(image=Image(torch.rand(2, 3, 64, 64))))


def test_without_a_count_it_behaves_as_stock() -> None:
    """With no expected image count the variant is stock Anomalib, list and all."""
    stock, ours = _models()
    batches = _batches()

    expected = _fit(stock, batches)
    bank = _fit(ours, batches)

    assert torch.equal(bank, expected)
    assert ours.embedding_rows == 384
    assert ours.coreset_seconds > 0


def test_fitting_with_nothing_embedded_is_an_error() -> None:
    """Selecting a coreset from no embeddings is refused."""
    _, ours = _models()
    ours.expected_images = 4

    with pytest.raises(ValueError, match="Embedding store is empty"):
        ours.fit()


def test_the_variant_keeps_anomalibs_defaults() -> None:
    """The variant is PatchCore as Anomalib ships it: backbone, layers, ratio, neighbours."""
    ours = inspect.signature(SingleCopyPatchcore).parameters
    stock = inspect.signature(Patchcore).parameters

    assert issubclass(SingleCopyPatchcore, Patchcore)
    assert {name: p.default for name, p in ours.items()} == {
        name: p.default for name, p in stock.items()
    }
    assert ours["backbone"].default == "wide_resnet50_2"
    assert tuple(ours["layers"].default) == ("layer2", "layer3")
    assert ours["coreset_sampling_ratio"].default == 0.1
    assert ours["num_neighbors"].default == 9
