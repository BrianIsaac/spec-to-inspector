"""The published PatchCore figures the measured AUROC is held against, and the plan's gate."""

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict

REFERENCE_SOURCE: Final = (
    "Rolih et al., 'Divide and Conquer: High-Resolution Industrial Anomaly Detection via "
    "Memory Efficient Tiled Ensemble', Table 7, PatchCore, single model at 256 px (SM256), "
    "March 2024; cited as the published reference, not as a current fact"
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
