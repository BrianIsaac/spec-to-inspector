"""Check the B70 machine: PyTorch XPU on each card, OpenVINO, and PatchCore on one board.

Run on the machine after `scripts/setup_xpu.sh`, from the repository root:

    UV_NO_SYNC=1 uv run python scripts/xpu_checks.py --out checks.json

The anomaly model goes on the first card, the one the plan gives it, and the
card's memory is read with `xpu-smi` while the model is resident, so that which
physical card it landed on is measured and not assumed.
"""

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import openvino
import torch

from spec_to_inspector.anomaly.infer import AnomalyModel, image_dataset, visa_test_items
from spec_to_inspector.device import describe_device, peak_memory, reset_peak_memory
from spec_to_inspector.settings import Settings

MATMUL_SIDE = 2048
SMOKE_PART = "pcb4"
SMOKE_BOARD = "bad-005"


def card_memory_mib(card: int) -> int | None:
    """Read one card's memory in use with `xpu-smi`.

    Args:
        card: The card's `xpu-smi` device number.

    Returns:
        The MiB in use, or None if it could not be read.
    """
    program = shutil.which("xpu-smi")
    if program is None:
        return None
    done = subprocess.run(
        [program, "stats", "-d", str(card)], capture_output=True, text=True, check=False
    )
    found = re.search(r"GPU Memory Used \(MiB\)\s+Tile 0: avg: (\d+)", done.stdout)
    return int(found.group(1)) if found else None


def check_cards() -> list[dict[str, object]]:
    """Describe each card and compute a matrix product on it, checked against the CPU.

    Returns:
        One record per card.
    """
    generator = torch.Generator().manual_seed(0)
    x = torch.randn(MATMUL_SIDE, MATMUL_SIDE, generator=generator)
    expected = x @ x
    cards: list[dict[str, object]] = []
    for index in range(torch.xpu.device_count()):
        target = torch.device("xpu", index)
        on_card = x.to(target)
        started = time.perf_counter()
        product = on_card @ on_card
        torch.xpu.synchronize(target)
        seconds = time.perf_counter() - started
        worst = float((product.cpu() - expected).abs().max() / expected.abs().max())
        cards.append(
            {
                "device": describe_device("xpu", index).model_dump(),
                "matmul": {
                    "side": MATMUL_SIDE,
                    "dtype": "float32",
                    "landed_on": str(product.device),
                    "seconds": seconds,
                    "worst_relative_difference_from_cpu": worst,
                },
            }
        )
    return cards


def check_openvino() -> dict[str, object]:
    """List the devices OpenVINO sees, by name.

    Returns:
        OpenVINO's version and its devices.
    """
    core = openvino.Core()
    return {
        "version": openvino.__version__,
        "devices": {
            device: core.get_property(device, "FULL_DEVICE_NAME")
            for device in core.available_devices
        },
    }


def check_patchcore(settings: Settings) -> dict[str, object]:
    """Score one board with the laptop's trained PatchCore, on the first card.

    A smoke test of the code path, with no claim about speed: the measured run
    is week 2's.

    Args:
        settings: Where the models and the data are.

    Returns:
        The score, the map's shape, the time and the memory.
    """
    before = {card: card_memory_mib(card) for card in (0, 1)}
    model = AnomalyModel.load(settings.models_dir, SMOKE_PART, device="xpu")
    item = next(
        found
        for found in visa_test_items(settings.visa_dir, SMOKE_PART)
        if found.image_id == SMOKE_BOARD
    )
    image, _ = image_dataset([item.path], model.resize)[0]
    reset_peak_memory(model.device)
    first_started = time.perf_counter()
    scores, maps = model.score(image.unsqueeze(0))
    first_seconds = time.perf_counter() - first_started
    second_started = time.perf_counter()
    model.score(image.unsqueeze(0))
    second_seconds = time.perf_counter() - second_started
    allocated, reserved = peak_memory(model.device)
    return {
        "part": SMOKE_PART,
        "board": SMOKE_BOARD,
        "model_device": str(scores.device),
        "score": float(scores[0]),
        "image_threshold": model.thresholds.image,
        "map_shape": list(maps.shape),
        "first_pass_seconds": first_seconds,
        "second_pass_seconds": second_seconds,
        "peak_allocated_bytes": allocated,
        "peak_reserved_bytes": reserved,
        "resident_bytes": model.resident_bytes,
        "card_memory_mib_before": before,
        "card_memory_mib_with_the_model": {card: card_memory_mib(card) for card in (0, 1)},
    }


def main() -> None:
    """Run the checks and write what they found."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()

    record = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "torch": torch.__version__,
        "xpu_available": torch.xpu.is_available(),
        "xpu_device_count": torch.xpu.device_count(),
        "cards": check_cards(),
        "openvino": check_openvino(),
        "patchcore": check_patchcore(Settings()),
    }
    text = json.dumps(record, indent=2) + "\n"
    arguments.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
