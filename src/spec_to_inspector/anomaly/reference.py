"""The published PatchCore figures the measured AUROC is held against, and the plan's gate."""

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict

REFERENCE_SOURCE: Final = (
    "Rolih, Ameln, Vaidya and Akcay, 'Divide and Conquer: High-Resolution Industrial Anomaly "
    "Detection via Memory Efficient Tiled Ensemble', arXiv 2403.04932: the table 'VisA results "
    "of all 6 setups for Patchcore' (Table 7 in v1 of 7 March 2024, Table 9 in v2 of 8 April "
    "2024), column 'Single model 256' (SM256), detection AUROC; cited as the published "
    "reference, not as a current fact"
)
REFERENCE_BACKBONE: Final = "resnet18"
"""The paper's backbone: "The backbone used in all setups is ResNet18"."""

REFERENCE_NOTE: Final = (
    "The paper's figures are the mean of 3 runs with a ResNet18 backbone, batch size 8, centre "
    "crop disabled. The product's PatchCore uses Anomalib's default wide_resnet50_2, so the "
    "comparison is to the published setting at the same resolution, not like for like in "
    "backbone. The paper's second figure per cell is AUPRO; it publishes no pixel AUROC. Its "
    "SM256 cells for PCB3 and PCB4 are identical (99.0/86.6) in both versions of the PDF."
)
PUBLISHED_IMAGE_AUROC: Final[Mapping[str, float]] = {
    "pcb1": 94.9,
    "pcb2": 92.4,
    "pcb3": 99.0,
    "pcb4": 99.0,
}
"""Image AUROC in points per VisA PCB category, as the plan's section 3.4 quotes the paper."""

GATE_POINTS: Final = 3.0
"""The plan's gate: a category may be at most this many points under its reference."""


class Comparison(BaseModel):
    """A measured image AUROC beside its published reference.

    Attributes:
        category: The category's name.
        measured_points: The measured image AUROC, in points (0 to 100).
        reference_points: The published image AUROC, in points.
        delta_points: Measured minus reference; negative when under.
        within_gate: Whether the measured figure is no more than `GATE_POINTS` under.
    """

    model_config = ConfigDict(frozen=True)

    category: str
    measured_points: float
    reference_points: float
    delta_points: float
    within_gate: bool


def compare(category: str, image_auroc: float) -> Comparison | None:
    """Hold a measured image AUROC against the published figure.

    Deltas are rounded to a hundredth of a point before the gate is applied,
    so a figure exactly 3 points under passes.

    Args:
        category: The category's name.
        image_auroc: The measured image AUROC, as a fraction of 1.

    Returns:
        The comparison, or None if nothing is published for the category.
    """
    reference = PUBLISHED_IMAGE_AUROC.get(category)
    if reference is None:
        return None
    measured = image_auroc * 100
    delta = round(measured - reference, 2)
    return Comparison(
        category=category,
        measured_points=measured,
        reference_points=reference,
        delta_points=delta,
        within_gate=delta >= -GATE_POINTS,
    )
