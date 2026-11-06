"""Tests for the device a run computes on."""

from collections.abc import Callable
from types import SimpleNamespace

import pytest
import torch

from spec_to_inspector.device import (
    ComputeDevice,
    describe_device,
    empty_cache,
    free_memory_bytes,
    peak_memory,
    release_memory,
    reset_peak_memory,
    synchronise,
)


def test_no_cuda_is_an_error_not_a_silent_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CUDA the description refuses, so no figure is measured on the CPU unawares."""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="CUDA is not available"):
        describe_device("cuda")


def test_no_xpu_is_an_error_not_a_silent_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without XPU the description refuses, and names the script that makes the environment."""
    monkeypatch.setattr(torch.xpu, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match=r"XPU is not available.*setup_xpu"):
        describe_device("xpu")


def test_an_intel_card_is_described_from_the_xpu_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """An Intel card has a name, memory and a runtime version, and none of CUDA's fields."""
    monkeypatch.setattr(torch.xpu, "is_available", lambda: True)
    monkeypatch.setattr(torch.xpu, "mem_get_info", lambda index: (1, 34_242_297_856))
    monkeypatch.setattr(torch.xpu, "get_device_name", lambda index: "Intel(R) Arc(TM) Pro B70")
    monkeypatch.setattr(
        torch.xpu,
        "get_device_properties",
        lambda index: SimpleNamespace(driver_version="1.15.38646+7"),
    )

    device = describe_device("xpu")

    assert device.kind == "xpu"
    assert device.name == "Intel(R) Arc(TM) Pro B70"
    assert device.total_memory_bytes == 34_242_297_856
    assert device.driver_version == "1.15.38646+7"
    assert device.capability is None
    assert device.cuda_version is None


def test_the_cpu_needs_no_accelerator(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CPU is described with neither accelerator present."""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.xpu, "is_available", lambda: False)

    device = describe_device("cpu")

    assert device.kind == "cpu"
    assert device.total_memory_bytes > 0


def test_a_record_written_before_the_choice_reads_as_cuda() -> None:
    """A device in a Stage I record, which has no kind, is CUDA's and still reads."""
    device = ComputeDevice.model_validate(
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5070 Ti Laptop GPU",
            "capability": [12, 0],
            "total_memory_bytes": 12_344_164_352,
            "torch_version": "2.14.1+cu130",
            "cuda_version": "13.0",
            "arch_list": ["sm_100", "sm_120"],
        }
    )

    assert device.kind == "cuda"
    assert device.capability == (12, 0)


def test_the_memory_counters_are_the_devices_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """XPU's memory is read from `torch.xpu`, and nothing there touches `torch.cuda`."""
    called: list[str] = []
    xpu = torch.device("xpu")

    def noting(name: str, value: object = None) -> Callable[..., object]:
        def stub(*_: object) -> object:
            called.append(name)
            return value

        return stub

    monkeypatch.setattr(torch.xpu, "synchronize", noting("synchronize"))
    monkeypatch.setattr(torch.xpu, "empty_cache", noting("empty_cache"))
    monkeypatch.setattr(torch.xpu, "reset_peak_memory_stats", noting("reset"))
    monkeypatch.setattr(torch.xpu, "max_memory_allocated", noting("allocated", 7))
    monkeypatch.setattr(torch.xpu, "max_memory_reserved", noting("reserved", 9))
    monkeypatch.setattr(torch.xpu, "mem_get_info", noting("free", (11, 13)))
    for name in ("synchronize", "empty_cache", "reset_peak_memory_stats", "max_memory_allocated"):
        monkeypatch.setattr(torch.cuda, name, noting(f"cuda {name}"))

    synchronise(xpu)
    empty_cache(xpu)
    reset_peak_memory(xpu)
    assert peak_memory(xpu) == (7, 9)
    assert free_memory_bytes(xpu) == 11
    release_memory(xpu)

    assert not [name for name in called if name.startswith("cuda")]
    assert called.count("empty_cache") == 2


def test_the_cpu_has_no_counters() -> None:
    """On the CPU nothing is waited for and memory reads as zero, not as an error."""
    cpu = torch.device("cpu")

    synchronise(cpu)
    empty_cache(cpu)
    reset_peak_memory(cpu)
    release_memory(cpu)

    assert peak_memory(cpu) == (0, 0)
    assert free_memory_bytes(cpu) == 0


@pytest.mark.gpu
def test_the_gpu_is_sm_120_and_computes(record_property: Callable[[str, object], None]) -> None:
    """The laptop's GPU reports capability (12, 0), the wheel carries sm_120, and it computes."""
    device = describe_device("cuda")
    record_property("cuda_device", device.model_dump_json())
    print(device.model_dump_json(indent=2))

    assert isinstance(device, ComputeDevice)
    assert device.capability == (12, 0)
    assert "sm_120" in device.arch_list
    assert device.cuda_version is not None
    assert device.cuda_version.startswith("13.")

    x = torch.arange(6, dtype=torch.float32, device="cuda").reshape(2, 3)
    product = (x @ x.T).cpu()

    assert torch.equal(product, torch.tensor([[5.0, 14.0], [14.0, 50.0]]))


@pytest.mark.xpu
def test_each_intel_card_is_a_b70_and_computes() -> None:
    """Every card this process sees is a B70 with its 32 GB, and computes."""
    assert torch.xpu.device_count() > 0

    for index in range(torch.xpu.device_count()):
        device = describe_device("xpu", index)
        assert "B70" in device.name
        assert device.total_memory_bytes > 30 * 2**30

        target = torch.device("xpu", index)
        x = torch.arange(6, dtype=torch.float32, device=target).reshape(2, 3)
        reset_peak_memory(target)
        product = x @ x.T
        allocated, reserved = peak_memory(target)

        assert torch.equal(product.cpu(), torch.tensor([[5.0, 14.0], [14.0, 50.0]]))
        assert 0 < allocated <= reserved
        assert 0 < free_memory_bytes(target) <= device.total_memory_bytes
