"""Tests for the PatchCore variant whose training embeddings wait in host memory."""

import inspect

import torch
from anomalib.data import ImageBatch
from anomalib.models import Patchcore
from lightning.pytorch import seed_everything
from torchvision.tv_tensors import Image

from spec_to_inspector.anomaly.model import HostBufferedPatchcore


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


def _models() -> tuple[Patchcore, HostBufferedPatchcore]:
    """Build stock PatchCore and the variant with the same weights, on a small backbone.

    Returns:
        Stock Anomalib's model and ours.
    """
    seed_everything(1)
    stock = Patchcore(backbone="resnet18", pre_trained=False, visualizer=False)
    seed_everything(1)
    ours = HostBufferedPatchcore(backbone="resnet18", pre_trained=False, visualizer=False)
    return stock, ours


def test_the_memory_bank_equals_stock_anomalibs() -> None:
    """Buffering on the host changes where the embeddings wait, not what the coreset is."""
    stock, ours = _models()
    seed_everything(2)
    batches = [torch.rand(2, 3, 64, 64) for _ in range(3)]

    expected = _fit(stock, batches)
    bank = _fit(ours, batches)

    assert bank.shape == (38, 384)
    assert torch.equal(bank, expected)


def test_embeddings_wait_on_the_host_and_are_released() -> None:
    """Each batch's embedding is held on the CPU, and none is left after the fit."""
    _, ours = _models()
    ours.train()

    ours.training_step(ImageBatch(image=Image(torch.rand(2, 3, 64, 64))))

    assert [e.device.type for e in ours.model.embedding_store] == ["cpu"]
    assert ours.embedding_rows == 0

    seed_everything(3)
    ours.fit()

    assert ours.model.embedding_store == []
    assert ours.embedding_rows == 128
    assert ours.coreset_seconds > 0
    assert ours.model.memory_bank.shape == (12, 384)


def test_the_variant_keeps_anomalibs_defaults() -> None:
    """The variant is PatchCore as Anomalib ships it: backbone, layers, ratio, neighbours."""
    ours = inspect.signature(HostBufferedPatchcore).parameters
    stock = inspect.signature(Patchcore).parameters

    assert issubclass(HostBufferedPatchcore, Patchcore)
    assert {name: p.default for name, p in ours.items()} == {
        name: p.default for name, p in stock.items()
    }
    assert ours["backbone"].default == "wide_resnet50_2"
    assert tuple(ours["layers"].default) == ("layer2", "layer3")
    assert ours["coreset_sampling_ratio"].default == 0.1
    assert ours["num_neighbors"].default == 9
