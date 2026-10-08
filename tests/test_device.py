"""Tests for the CUDA device description."""

from collections.abc import Callable

import pytest
import torch

from spec_to_inspector.device import CudaDevice, cuda_device


def test_no_cuda_is_an_error_not_a_silent_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CUDA the description refuses, so no figure is measured on the CPU unawares."""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="CUDA is not available"):
        cuda_device()


@pytest.mark.gpu
def test_the_gpu_is_sm_120_and_computes(record_property: Callable[[str, object], None]) -> None:
    """The laptop's GPU reports capability (12, 0), the wheel carries sm_120, and it computes."""
    device = cuda_device()
    record_property("cuda_device", device.model_dump_json())
    print(device.model_dump_json(indent=2))

    assert isinstance(device, CudaDevice)
    assert device.capability == (12, 0)
    assert "sm_120" in device.arch_list
    assert device.cuda_version is not None
    assert device.cuda_version.startswith("13.")

    x = torch.arange(6, dtype=torch.float32, device="cuda").reshape(2, 3)
    product = (x @ x.T).cpu()

    assert torch.equal(product, torch.tensor([[5.0, 14.0], [14.0, 50.0]]))
