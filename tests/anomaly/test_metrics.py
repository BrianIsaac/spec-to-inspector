"""Tests for the exact AUROC of raw scores."""

import numpy as np
import pytest
import torch
from torchmetrics.functional.classification import binary_auroc

from spec_to_inspector.anomaly.metrics import auroc


def test_auroc_is_the_share_of_pairs_ranked_the_right_way() -> None:
    """With 2 anomalous and 3 normal scores, 4 of the 6 pairs are in order."""
    scores = [0.13, 0.26, 0.08, 0.92, 0.03]
    anomalous = [False, False, True, True, False]

    assert auroc(scores, anomalous) == pytest.approx(4 / 6)


def test_raw_patchcore_scores_are_not_squashed() -> None:
    """Scores in the tens keep their order; a sigmoid would tie them all at 1.

    torchmetrics applies a sigmoid to scores outside [0, 1], which rounds every
    PatchCore distance above about 37 to exactly 1.0 and so ties them. That is
    the fault this function replaces.
    """
    scores = [40.0, 50.0, 60.0, 45.0, 55.0, 65.0]
    anomalous = [False, False, False, True, True, True]

    assert auroc(scores, anomalous) == pytest.approx(6 / 9)
    squashed = binary_auroc(torch.tensor(scores, dtype=torch.float64), torch.tensor(anomalous))
    assert float(squashed) == 0.5


def test_ties_count_half() -> None:
    """A normal and an anomalous image with the same score are half a correct pair."""
    assert auroc([1.0, 1.0], [False, True]) == 0.5
    assert auroc([1.0, 2.0, 2.0, 3.0], [False, False, True, True]) == pytest.approx(3.5 / 4)


def test_perfect_and_inverted_orders() -> None:
    """Every anomalous score above every normal one is 1; the reverse is 0."""
    assert auroc([1.0, 2.0, 3.0, 4.0], [False, False, True, True]) == 1.0
    assert auroc([1.0, 2.0, 3.0, 4.0], [True, True, False, False]) == 0.0


@pytest.mark.parametrize("anomalous", [[], [True, True], [False, False, False]])
def test_one_class_has_no_auroc(anomalous: list[bool]) -> None:
    """Without both normal and anomalous images there is nothing to rank."""
    assert auroc([float(i) for i in range(len(anomalous))], anomalous) is None


def test_auroc_equals_torchmetrics_on_scores_inside_the_unit_interval() -> None:
    """On scores a sigmoid is not applied to, the two computations agree."""
    rng = np.random.default_rng(5)
    scores = rng.random(400).round(2)
    anomalous = rng.random(400) < 0.5 * (scores + 0.5)

    expected = binary_auroc(torch.tensor(scores), torch.tensor(anomalous))

    assert auroc(scores.tolist(), anomalous.tolist()) == pytest.approx(float(expected), abs=1e-6)


def test_scores_and_labels_must_pair_up() -> None:
    """A score without a label is refused."""
    with pytest.raises(ValueError, match="2 scores"):
        auroc([1.0, 2.0], [True])
