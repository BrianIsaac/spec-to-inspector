"""The device a run computes on: chosen in the settings, described for the record.

`cuda` is the laptop's NVIDIA card, `xpu` an Intel Arc card through PyTorch's
XPU build, and `cpu` needs neither. `torch.cuda` and `torch.xpu` keep the same
memory counters, so the helpers here are what the rest of the code calls.

On a machine with several Intel cards the process is given one with
`ZE_AFFINITY_MASK`, or it takes the first it sees: nothing here picks a card.
"""

import gc
import os
import platform

import torch
from pydantic import BaseModel, ConfigDict

from spec_to_inspector.settings import DeviceKind


class ComputeDevice(BaseModel):
    """One device and the PyTorch build driving it.

    Attributes:
        kind: What it is. Records written before there was a choice are CUDA's
            and do not say so.
        index: The device's index among those of its kind.
        name: The device's marketing name.
        capability: CUDA's compute capability, (12, 0) for sm_120; None off CUDA.
        total_memory_bytes: The device's memory as PyTorch reports it.
        torch_version: The installed PyTorch, with its local build tag.
        cuda_version: The CUDA version PyTorch was built against; None off CUDA.
        arch_list: The architectures the PyTorch build carries kernels for.
        driver_version: The compute runtime's version, as the XPU build reports
            it; None off XPU.
    """

    model_config = ConfigDict(frozen=True)

    kind: DeviceKind = "cuda"
    index: int
    name: str
    capability: tuple[int, int] | None = None
    total_memory_bytes: int
    torch_version: str
    cuda_version: str | None = None
    arch_list: tuple[str, ...] = ()
    driver_version: str | None = None


def _cuda_device(index: int) -> ComputeDevice:
    """Describe a CUDA device.

    Args:
        index: The device's CUDA index.

    Returns:
        The device and the PyTorch build driving it.

    Raises:
        RuntimeError: If CUDA is not available to this PyTorch.
    """
    if not torch.cuda.is_available():
        msg = (
            "CUDA is not available: check the driver and that torch is the cu130 build, "
            f"not {torch.__version__}"
        )
        raise RuntimeError(msg)
    _, total_memory_bytes = torch.cuda.mem_get_info(index)
    return ComputeDevice(
        kind="cuda",
        index=index,
        name=torch.cuda.get_device_name(index),
        capability=torch.cuda.get_device_capability(index),
        total_memory_bytes=total_memory_bytes,
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda,
        arch_list=tuple(torch.cuda.get_arch_list()),
    )


def _xpu_device(index: int) -> ComputeDevice:
    """Describe an Intel XPU device.

    Args:
        index: The device's XPU index, among the cards this process can see.

    Returns:
        The device and the PyTorch build driving it.

    Raises:
        RuntimeError: If XPU is not available to this PyTorch.
    """
    if not torch.xpu.is_available():
        msg = (
            "XPU is not available: check the driver and that torch is the xpu build "
            f"(scripts/setup_xpu.sh), not {torch.__version__}"
        )
        raise RuntimeError(msg)
    _, total_memory_bytes = torch.xpu.mem_get_info(index)
    return ComputeDevice(
        kind="xpu",
        index=index,
        name=torch.xpu.get_device_name(index),
        total_memory_bytes=total_memory_bytes,
        torch_version=torch.__version__,
        # PyTorch's binding has no stub for what this returns.
        driver_version=str(torch.xpu.get_device_properties(index).driver_version),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    )


def _cpu_device() -> ComputeDevice:
    """Describe the CPU.

    Returns:
        The machine's processor and memory, and the PyTorch build.
    """
    return ComputeDevice(
        kind="cpu",
        index=0,
        name=platform.processor() or platform.machine(),
        total_memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        torch_version=torch.__version__,
    )


def describe_device(kind: DeviceKind = "cuda", index: int = 0) -> ComputeDevice:
    """Describe a device, refusing one this PyTorch cannot reach.

    Args:
        kind: The accelerator asked for.
        index: The device's index among those of its kind; the CPU has only 0.

    Returns:
        The device and the PyTorch build driving it.

    Raises:
        RuntimeError: If the accelerator is not available, so that no figure is
            measured on the CPU unawares.
    """
    if kind == "cuda":
        return _cuda_device(index)
    if kind == "xpu":
        return _xpu_device(index)
    return _cpu_device()


def synchronise(device: torch.device) -> None:
    """Wait for a device's queued work, so that a clock reading means what it says.

    Args:
        device: The device; the CPU has no queue.
    """
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "xpu":
        torch.xpu.synchronize(device)


def empty_cache(device: torch.device) -> None:
    """Return a device's cached blocks to the driver.

    Args:
        device: The device; the CPU keeps no such cache.
    """
    if device.type == "cuda":
        torch.cuda.empty_cache()
    elif device.type == "xpu":
        torch.xpu.empty_cache()


def reset_peak_memory(device: torch.device) -> None:
    """Restart a device's peak memory counters.

    Args:
        device: The device; the CPU has none.
    """
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    elif device.type == "xpu":
        torch.xpu.reset_peak_memory_stats(device)


def peak_memory(device: torch.device) -> tuple[int, int]:
    """Read a device's peak memory since its counters last restarted.

    Args:
        device: The device.

    Returns:
        The peak allocated and reserved bytes; zeros on the CPU, which has no
        such counters.
    """
    synchronise(device)
    if device.type == "cuda":
        return torch.cuda.max_memory_allocated(device), torch.cuda.max_memory_reserved(device)
    if device.type == "xpu":
        return torch.xpu.max_memory_allocated(device), torch.xpu.max_memory_reserved(device)
    return 0, 0


def free_memory_bytes(device: torch.device) -> int:
    """Read how much of a device's memory is free.

    Args:
        device: The device.

    Returns:
        The free bytes the driver reports; zero on the CPU, which is not measured.
    """
    if device.type == "cuda":
        return torch.cuda.mem_get_info(device)[0]
    if device.type == "xpu":
        return torch.xpu.mem_get_info(device)[0]
    return 0


def release_memory(device: torch.device) -> None:
    """Collect what is no longer referred to and hand the device's cached memory back.

    Args:
        device: The device.
    """
    gc.collect()
    empty_cache(device)
