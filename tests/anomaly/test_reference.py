"""Tests for the comparison against the published PatchCore figures and the plan's gate."""

import pytest

from spec_to_inspector.anomaly.reference import (
    GATE_POINTS,
    PUBLISHED_IMAGE_AUROC,
    compare,
)


def test_the_published_figures_are_the_plans() -> None:
    """The reference is the Anomalib team's own PatchCore at 256 px, per category."""
    assert PUBLISHED_IMAGE_AUROC == {"pcb1": 94.9, "pcb2": 92.4, "pcb3": 99.0, "pcb4": 99.0}
    assert GATE_POINTS == 3.0


@pytest.mark.parametrize(
    ("auroc", "delta", "within"),
    [
        (0.9857, -0.43, True),
        (0.99, 0.0, True),
        (0.96, -3.0, True),
        (0.9599, -3.01, False),
        (1.0, 1.0, True),
        (0.90, -9.0, False),
    ],
)
def test_a_category_is_within_the_gate_up_to_three_points_under(
    auroc: float, delta: float, within: bool
) -> None:
    """The gate is a shortfall of more than 3 points; a figure above the reference passes."""
    comparison = compare("pcb4", auroc)

    assert comparison is not None
    assert comparison.reference_points == 99.0
    assert comparison.measured_points == pytest.approx(auroc * 100)
    assert comparison.delta_points == pytest.approx(delta, abs=1e-9)
    assert comparison.within_gate is within


def test_a_category_without_a_published_figure_has_no_comparison() -> None:
    """There is nothing to compare a category the reference does not cover."""
    assert compare("candle", 0.99) is None
