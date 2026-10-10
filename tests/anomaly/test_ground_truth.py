"""Tests for reading VisA's defect types out of its ground-truth masks."""

import csv

import numpy as np
import pytest
from PIL import Image

from spec_to_inspector.anomaly.ground_truth import VISA_MASK_VALUES, defect_types
from spec_to_inspector.datasets.visa import NORMAL_LABEL, PUBLISHED_COUNTS
from spec_to_inspector.settings import Settings


def test_every_pcb_categorys_defect_types_have_a_mask_value() -> None:
    """The table covers exactly the defect types U1 counted in each `image_anno.csv`."""
    for category, counts in PUBLISHED_COUNTS.items():
        assert set(VISA_MASK_VALUES[category].values()) == set(counts.defect_types)
        assert 0 not in VISA_MASK_VALUES[category]


def test_mask_values_become_defect_types() -> None:
    """A region's mask values name its defect types, in value order."""
    assert defect_types("pcb1", [2]) == ["melt"]
    assert defect_types("pcb4", [7, 3]) == ["missing", "dirt"]
    assert defect_types("pcb4", []) == []


def test_an_unknown_value_or_category_is_an_error() -> None:
    """A value the table does not hold is never guessed at."""
    with pytest.raises(ValueError, match="9"):
        defect_types("pcb1", [9])
    with pytest.raises(ValueError, match="candle"):
        defect_types("candle", [1])


@pytest.mark.data
def test_the_table_holds_on_every_anomalous_image_of_the_fetched_data() -> None:
    """In all 400 masks, the non-zero values are exactly the label's defect types."""
    root = Settings().visa_dir
    checked = 0
    for category in PUBLISHED_COUNTS:
        with (root / category / "image_anno.csv").open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["label"] != NORMAL_LABEL]
        for row in rows:
            labelled = {part.strip() for part in row["label"].split(",") if part.strip()}
            with Image.open(root / row["mask"]) as mask:
                values = [int(value) for value in np.unique(np.asarray(mask)) if value]
            assert set(defect_types(category, values)) == labelled, row["image"]
            checked += 1
    assert checked == 400
