"""What VisA's ground-truth masks say beyond "defect here": which defect.

In VisA's own masks (`<category>/Data/Masks/Anomaly/*.png`, 8-bit) a pixel's
value is its defect type, not a flag: 0 is background and each type of the
category has one value. On all 400 anomalous images of the four PCB
categories the non-zero values of a mask are exactly the defect types its
`image_anno.csv` label names (checked by a `data` test). So a region of the
anomaly map can be given the defect type of the ground truth under it, also
in an image that carries several defects.

Anomalib's split binarises the masks to 0 and 255 and loses this; the values
here are read from the fetched masks.
"""

from collections.abc import Iterable, Mapping
from typing import Final

VISA_MASK_VALUES: Final[Mapping[str, Mapping[int, str]]] = {
    "pcb1": {1: "bent", 2: "melt", 3: "scratch", 4: "missing"},
    "pcb2": {1: "bent", 2: "melt", 3: "scratch", 4: "missing"},
    "pcb3": {1: "bent", 2: "melt", 3: "scratch", 4: "missing"},
    "pcb4": {
        1: "burnt",
        2: "scratch",
        3: "missing",
        4: "damage",
        5: "extra",
        6: "wrong place",
        7: "dirt",
    },
}
"""Per PCB category, the defect type each non-zero mask value stands for, spelled as VisA does."""


def defect_types(category: str, values: Iterable[int]) -> list[str]:
    """Name the defect types of some ground-truth mask values.

    Args:
        category: The VisA category the mask belongs to.
        values: Non-zero mask values, such as a region's `ground_truth_values`.

    Returns:
        The defect types, in order of mask value.

    Raises:
        ValueError: If the category or a value is not in the table.
    """
    table = VISA_MASK_VALUES.get(category)
    if table is None:
        msg = f"no mask values are known for the category {category}"
        raise ValueError(msg)
    unknown = sorted(set(values) - set(table))
    if unknown:
        msg = f"{category} masks hold no defect type for the values {unknown}"
        raise ValueError(msg)
    return [table[value] for value in sorted(set(values))]
