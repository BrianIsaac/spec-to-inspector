"""Reading the GPU's memory from `nvidia-smi` in a process that forks.

The judge's own sampler reads `nvidia-smi` through a pipe, which is right
where nothing forks. The bench samples while the anomaly model's data loader
forks its workers, and a worker forked while a reading is under way inherits
the pipe's write end and keeps it open until it exits: the reading then waits
for an end of file that comes when the scoring is over. The bench's first
whole run got one reading in 17 seconds that way.

So the program is started here with `posix_spawn` and writes to a temporary
file: there is no pipe, and nothing is waited on but the program's own exit.
"""

import shutil
from typing import Final

from spec_to_inspector.card_memory import DEFAULT_TIMEOUT_SECONDS, output_without_pipe
from spec_to_inspector.judge.timing import GpuReading, parse_nvidia_smi

_QUERIES: Final = ("--query-gpu=memory.used", "--query-compute-apps=pid,used_memory")


def read_gpu_memory(
    pid: int | None,
    *,
    program: str | None = shutil.which("nvidia-smi"),
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> GpuReading:
    """Read the card's memory in use and one process's own, without a pipe.

    Args:
        pid: The process whose own memory is wanted, or None for none.
        program: The path of `nvidia-smi`; None where there is none.
        timeout_seconds: How long each of the two queries may take.

    Returns:
        The reading; both figures None if the program is absent, fails or
        hangs, and the process's None if it holds nothing on the card.
    """
    if program is None:
        return GpuReading(None, None)
    outputs: list[str] = []
    for query in _QUERIES:
        printed = output_without_pipe(
            [program, query, "--format=csv,noheader,nounits"], timeout_seconds
        )
        if printed is None:
            return GpuReading(None, None)
        outputs.append(printed)
    return parse_nvidia_smi(outputs[0], outputs[1], pid)
