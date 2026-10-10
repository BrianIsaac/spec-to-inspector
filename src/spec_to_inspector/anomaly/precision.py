"""Full float32 on NVIDIA cards, so a score does not depend on its batch.

PyTorch lets cuDNN run float32 convolutions in TF32 by default: a 10-bit
mantissa inside the multiply, about three significant figures. Which kernel
cuDNN picks depends on the batch's shape, so with TF32 on, one image's
PatchCore score moves with the number of images scored beside it: by up to
0.085 raw units between batch 1 and batch 32 on PCB2 (measured, 10 October
2026), against a threshold near 30. With TF32 off the same comparison gives
0.0002, and batch 16 against batch 32 gives exactly 0.

An inspector whose verdict on a board near the threshold depends on how many
boards were in the batch is not defensible, so training and inference here
run in full float32. It is also what a card without TF32 computes, the
Intel Arc B70 included.
"""

from collections.abc import Generator
from contextlib import contextmanager

import torch


@contextmanager
def full_float32(*, enabled: bool = True) -> Generator[None]:
    """Forbid TF32 in cuDNN convolutions and CUDA matrix products for the duration.

    Args:
        enabled: Whether to forbid it; false leaves the process as it is, for a
            model whose thresholds were chosen with TF32 on.

    Yields:
        Nothing; both flags are restored on exit.
    """
    if not enabled:
        yield
        return
    convolutions = torch.backends.cudnn.allow_tf32
    products = torch.backends.cuda.matmul.allow_tf32
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    try:
        yield
    finally:
        torch.backends.cudnn.allow_tf32 = convolutions
        torch.backends.cuda.matmul.allow_tf32 = products
