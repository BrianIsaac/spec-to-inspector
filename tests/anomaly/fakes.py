"""A synthetic VisA tree with decodable images and masks, for the anomaly tests."""

from pathlib import Path

import cv2
import numpy as np

from tests.datasets.visa_fakes import FAKE, KEPT, fake_files, write_tree

IMAGE_SIZE = (48, 64)
"""Height and width of every synthetic image, deliberately not square."""


def _is_mask(member: str) -> bool:
    return "/Masks/" in member


def _is_image(member: str) -> bool:
    return "/Images/" in member


def write_visa(root: Path, *, kept_only: bool = True) -> None:
    """Write the synthetic VisA of `visa_fakes` with real JPEG images and PNG masks.

    Each mask carries VisA's convention: 0 for background and a small defect
    index (1, 2, ...) per defect, never 255, so a test can tell a binarised
    mask from a copied one.

    Args:
        root: The dataset directory to write under.
        kept_only: Whether to leave out the non-PCB category, as `data fetch` does;
            its rows stay in the split CSV either way.
    """
    files = fake_files()
    if kept_only:
        files = {
            member: content
            for member, content in files.items()
            if member.split("/", 1)[0] in KEPT or member.startswith("split_csv/")
        }
    write_tree(root, files)
    height, width = IMAGE_SIZE
    rng = np.random.default_rng(7)
    for member in files:
        path = root / member
        if _is_mask(member):
            mask = np.zeros((height, width), dtype=np.uint8)
            mask[4:12, 6:20] = 1
            mask[30:40, 40:50] = 2
            assert cv2.imwrite(str(path), mask)
        elif _is_image(member):
            image = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
            assert cv2.imwrite(str(path), image)


def categories() -> tuple[str, ...]:
    """The PCB categories of the synthetic VisA.

    Returns:
        The category names, sorted.
    """
    return tuple(sorted(name for name in FAKE if name in KEPT))
