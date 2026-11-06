"""One reading of a card's memory, and how it is taken on an Intel card, from `xpu-smi`.

`nvidia-smi`'s readers are the laptop's: `judge.timing` and `bench.gpu`. The one here gives the same
`GpuReading` from `xpu-smi`, and is chosen where the configured device is `xpu`.

**Which card.** `xpu-smi` numbers the cards as Level Zero shows them to it, so it obeys
`ZE_AFFINITY_MASK`: measured with the judge on the second card, `xpu-smi --id=0` reads the first
card under mask 0 and the second under mask 1. So `--id=0` in this process's own environment is the
card PyTorch calls `xpu:0`, whatever the mask, and a card outside the process, such as the judge's,
is named by its PCI address, which does not move.

**Which process.** `xpu-smi ps` lists this process's own, but not the judge's server in its
container, not even under `sudo` (measured), so a process's own figure can be None while its
card's is known.

No pipe is used, for the reason in `bench.gpu`: the bench samples while a data loader forks.
"""

import contextlib
import json
import os
import shutil
import signal
import tempfile
import time
from collections.abc import Mapping, Sequence
from typing import Final, NamedTuple, cast

DEFAULT_TIMEOUT_SECONDS: Final = 5.0
FIRST_VISIBLE_CARD: Final = "0"
"""What `xpu-smi` calls the first card this process can see, which is PyTorch's `xpu:0`."""
_MASK: Final = "ZE_AFFINITY_MASK"
_NOT_AVAILABLE: Final = "N/A"
_POLL_SECONDS: Final = 0.01
_KIB_PER_MIB: Final = 1024


class GpuReading(NamedTuple):
    """One reading of a card's memory.

    Attributes:
        gpu_used_mib: Memory in use on the card, or None if unreadable.
        server_mib: Memory the process asked about holds, or None if the
            process is not known or not among the card's.
    """

    gpu_used_mib: int | None
    server_mib: int | None


def output_without_pipe(
    arguments: Sequence[str],
    timeout_seconds: float,
    *,
    environment: Mapping[str, str] | None = None,
) -> str | None:
    """Run a program with its output in a temporary file, and give what it printed.

    Args:
        arguments: The program's path and its arguments.
        timeout_seconds: How long the program may take.
        environment: The program's environment; this process's if None.

    Returns:
        Its standard output, or None if it could not be started, failed, or
        was ended at the timeout.
    """
    with tempfile.TemporaryFile() as printed, open(os.devnull, "rb+") as nothing:  # noqa: PTH123
        actions = [
            (os.POSIX_SPAWN_DUP2, nothing.fileno(), 0),
            (os.POSIX_SPAWN_DUP2, printed.fileno(), 1),
            (os.POSIX_SPAWN_DUP2, nothing.fileno(), 2),
        ]
        try:
            pid = os.posix_spawn(
                arguments[0],
                list(arguments),
                os.environ if environment is None else environment,
                file_actions=actions,
            )
        except OSError:
            return None
        deadline = time.monotonic() + timeout_seconds
        while True:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
            if time.monotonic() >= deadline:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                return None
            time.sleep(_POLL_SECONDS)
        if os.waitstatus_to_exitcode(status) != 0:
            return None
        printed.seek(0)
        return printed.read().decode(errors="replace")


def _used_mib(text: str) -> int | None:
    """Read the memory in use from `xpu-smi --query-gpu=memory.used`.

    Args:
        text: Its output in CSV without a header or units: a decimal, such as `1307.2109375`.

    Returns:
        The whole MiB, or None for anything else, such as `N/A`.
    """
    try:
        return round(float(text.strip()))
    except ValueError:
        return None


def _process_mib(text: str, pid: int) -> int | None:
    """Read one process's memory from `xpu-smi ps -j`.

    Args:
        text: Its JSON output, which gives `mem_size` in KiB, for all that its help says kB:
            measured at 1,295,428 against the 1,295,304 KiB the driver's own `drm-total-vram0` gave.
        pid: The process.

    Returns:
        The whole MiB, or None if the process is not listed or the output cannot be read.
    """
    try:
        listing: object = json.loads(text)
    except ValueError:
        return None
    if not isinstance(listing, dict):
        return None
    rows = cast("dict[str, object]", listing).get("device_util_by_proc_list")
    if not isinstance(rows, list):
        return None
    for row in cast("list[object]", rows):
        if not isinstance(row, dict):
            continue
        entry = cast("dict[str, object]", row)
        size = entry.get("mem_size")
        if entry.get("process_id") == pid and isinstance(size, int):
            return round(size / _KIB_PER_MIB)
    return None


def _query(
    field: str,
    card: str,
    program: str | None,
    timeout_seconds: float,
    environment: Mapping[str, str] | None = None,
) -> str | None:
    """Ask `xpu-smi` for one text field of a card.

    Args:
        field: The field's name.
        card: The card, as `xpu-smi` takes it.
        program: The path of `xpu-smi`; None where there is none.
        timeout_seconds: How long the query may take.
        environment: The program's environment; this process's if None.

    Returns:
        The field, or None if the program is absent, fails, prints nothing or prints `N/A`.
    """
    if program is None:
        return None
    printed = output_without_pipe(
        [program, f"--query-gpu={field}", f"--id={card}", "--format=csv,noheader"],
        timeout_seconds,
        environment=environment,
    )
    text = (printed or "").strip()
    return None if text in {"", _NOT_AVAILABLE} else text


def read_xpu_name(
    *,
    card: str = FIRST_VISIBLE_CARD,
    program: str | None = shutil.which("xpu-smi"),
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Read an Intel card's name, whichever cards this process's mask lets it see.

    Measured under `ZE_AFFINITY_MASK=0`: for a card the mask hides, `xpu-smi` still reads
    `memory.used` by its PCI address but prints `N/A` for its name, and exits 0. So the name is
    read with the mask taken out of the query's environment, and nothing else.

    Args:
        card: The card, as `xpu-smi` takes it: an index, or a PCI address.
        program: The path of `xpu-smi`; None where there is none.
        timeout_seconds: How long the query may take.

    Returns:
        The name, or None if it cannot be read.
    """
    unmasked = {key: value for key, value in os.environ.items() if key != _MASK}
    return _query("name", card, program, timeout_seconds, unmasked)


def read_xpu_address(
    *,
    program: str | None = shutil.which("xpu-smi"),
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Read the PCI address of the first card this process can see, which is PyTorch's `xpu:0`.

    Args:
        program: The path of `xpu-smi`; None where there is none.
        timeout_seconds: How long the query may take.

    Returns:
        The address, or None if it cannot be read.
    """
    return _query("pci.bus_id", FIRST_VISIBLE_CARD, program, timeout_seconds)


def read_xpu_memory(
    pid: int | None,
    *,
    card: str = FIRST_VISIBLE_CARD,
    program: str | None = shutil.which("xpu-smi"),
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> GpuReading:
    """Read an Intel card's memory in use and one process's own, without a pipe.

    Args:
        pid: The process whose own memory is wanted, or None for none.
        card: The card, as `xpu-smi` takes it: an index among the cards this process can see, or
            a PCI address.
        program: The path of `xpu-smi`; None where there is none.
        timeout_seconds: How long each of the two queries may take.

    Returns:
        The reading; both figures None if the program is absent, fails or hangs on the card's
        query, and the process's None if it is not listed on the card.
    """
    if program is None:
        return GpuReading(None, None)
    used = output_without_pipe(
        [program, "--query-gpu=memory.used", f"--id={card}", "--format=csv,noheader,nounits"],
        timeout_seconds,
    )
    if used is None:
        return GpuReading(None, None)
    process: int | None = None
    if pid is not None:
        listed = output_without_pipe([program, "ps", "--id", card, "-j"], timeout_seconds)
        process = None if listed is None else _process_mib(listed, pid)
    return GpuReading(gpu_used_mib=_used_mib(used), server_mib=process)
