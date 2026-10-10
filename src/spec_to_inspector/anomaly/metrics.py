"""The area under the ROC curve of raw scores, computed exactly from ranks.

PatchCore's scores are distances in the tens. torchmetrics' `binary_auroc`
applies a sigmoid to any score outside [0, 1], which rounds every distance
above about 37 to exactly 1.0 and ties them; Anomalib avoids this by scoring
its normalised values. Raw scores are what the pipeline keeps, so their AUROC
is computed here without passing through anything that can saturate.
"""

from collections.abc import Sequence

import numpy as np


def auroc(scores: Sequence[float], anomalous: Sequence[bool]) -> float | None:
    """The probability that an anomalous image outscores a normal one.

    This is the Mann-Whitney statistic: over every pair of one anomalous and
    one normal score, the share ranked the right way, a tie counting half. It
    equals the area under the ROC curve.

    Args:
        scores: The scores, higher meaning more anomalous.
        anomalous: Whether each score belongs to an anomalous image.

    Returns:
        The AUROC in [0, 1], or None if the scores are all of one class.

    Raises:
        ValueError: If the two sequences differ in length.
    """
    if len(scores) != len(anomalous):
        msg = f"{len(scores)} scores but {len(anomalous)} labels"
        raise ValueError(msg)
    values = np.asarray(scores, dtype=np.float64)
    positive = np.asarray(anomalous, dtype=bool)
    positives = int(positive.sum())
    negatives = positive.size - positives
    if positives == 0 or negatives == 0:
        return None

    order = np.argsort(values, kind="stable")
    ranks = np.empty(values.size, dtype=np.float64)
    ranks[order] = np.arange(1, values.size + 1, dtype=np.float64)
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    rank_sums = np.bincount(inverse, weights=ranks)
    tied_ranks = (rank_sums / counts)[inverse]
    statistic = float(tied_ranks[positive].sum()) - positives * (positives + 1) / 2
    return statistic / (positives * negatives)
