"""Tests for running the model in full float32."""

import pytest
import torch

from spec_to_inspector.anomaly.precision import full_float32


@pytest.mark.parametrize("before", [True, False])
def test_tf32_is_off_inside_and_restored_after(
    before: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside the block neither convolutions nor matrix products may use TF32."""
    monkeypatch.setattr(torch.backends.cudnn, "allow_tf32", before)
    monkeypatch.setattr(torch.backends.cuda.matmul, "allow_tf32", before)

    with full_float32():
        assert torch.backends.cudnn.allow_tf32 is False
        assert torch.backends.cuda.matmul.allow_tf32 is False

    assert torch.backends.cudnn.allow_tf32 is before
    assert torch.backends.cuda.matmul.allow_tf32 is before


def test_the_flags_are_restored_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exception inside the block does not leave the process in another precision."""
    monkeypatch.setattr(torch.backends.cudnn, "allow_tf32", True)
    monkeypatch.setattr(torch.backends.cuda.matmul, "allow_tf32", True)

    with pytest.raises(RuntimeError, match="boom"), full_float32():
        raise RuntimeError("boom")

    assert torch.backends.cudnn.allow_tf32 is True
    assert torch.backends.cuda.matmul.allow_tf32 is True


def test_it_can_be_switched_off_for_a_model_trained_in_tf32() -> None:
    """With `enabled=False` the block leaves the process's precision alone."""
    before = (torch.backends.cudnn.allow_tf32, torch.backends.cuda.matmul.allow_tf32)

    with full_float32(enabled=False):
        assert (torch.backends.cudnn.allow_tf32, torch.backends.cuda.matmul.allow_tf32) == before
