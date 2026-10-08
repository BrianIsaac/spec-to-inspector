"""The CUDA device a run measures on, described for the record."""

import torch
from pydantic import BaseModel, ConfigDict


class CudaDevice(BaseModel):
    """One CUDA device and the PyTorch build driving it.

    Attributes:
        index: The device's CUDA index.
        name: The device's marketing name.
        capability: The compute capability, (12, 0) for sm_120.
        total_memory_bytes: The device's memory as CUDA reports it.
        torch_version: The installed PyTorch, with its local build tag.
        cuda_version: The CUDA version PyTorch was built against.
        arch_list: The architectures the PyTorch build carries kernels for.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    name: str
    capability: tuple[int, int]
    total_memory_bytes: int
    torch_version: str
    cuda_version: str | None
    arch_list: tuple[str, ...]


def cuda_device(index: int = 0) -> CudaDevice:
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
    return CudaDevice(
        index=index,
        name=torch.cuda.get_device_name(index),
        capability=torch.cuda.get_device_capability(index),
        total_memory_bytes=total_memory_bytes,
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda,
        arch_list=tuple(torch.cuda.get_arch_list()),
    )
