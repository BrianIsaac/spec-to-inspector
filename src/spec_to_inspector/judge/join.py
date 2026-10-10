"""The join of three units' models: the specification, the anomaly regions, the measurement.

The specification (`spec.schema`) declares zones, calibrations and clauses in
the document's terms; the measurement (`measure`) and the disposition rule
(`judge.disposition`) each take their own small models. This module is the
one place the first is turned into the second, so the conversions are stated
once: a clause for `any` zone has no zone in the rule; the scale is the
imaged width over the image's pixels, because the board does not fill the
frame; one region of the anomaly model's label image is measured alone, so
its crop, its score and its size stay those of one region.
"""

import numpy as np
from numpy.typing import NDArray

from spec_to_inspector.judge import disposition
from spec_to_inspector.measure import (
    CalibratedMask,
    Calibration,
    MeasuredRegion,
    Zone,
    ZoneMap,
    measure_regions,
)
from spec_to_inspector.spec import schema
from spec_to_inspector.spec.schema import ANY_ZONE, Specification


class JoinError(ValueError):
    """The specification and an image's inference do not fit together."""


def rule_clause(clause: schema.Clause) -> disposition.Clause:
    """Give a clause of the specification as the disposition rule takes it.

    A clause that refers a defect for review is given the rule as a reject:
    the rule settles whether the clause's condition holds, and the caller
    words what follows from a referral.

    Args:
        clause: The clause as the specification holds it.

    Returns:
        The clause's id, class, zone (None for any zone), limit, unit and
        comparison, unchanged in value.
    """
    return disposition.Clause(
        id=clause.id,
        defect_class=clause.defect_class,
        zone=None if clause.zone == ANY_ZONE else clause.zone,
        limit=clause.limit,
        unit=None if clause.unit is None else clause.unit.value,
        comparison=disposition.Comparison(clause.comparison.value),
        disposition=disposition.Outcome.REJECT,
    )


def zone_map_for(specification: Specification, category: str) -> ZoneMap:
    """Give a part's zones as the measurement takes them.

    Args:
        specification: The parsed specification.
        category: The part.

    Returns:
        The part's zones with their ranks; empty for a part without zones.
    """
    return ZoneMap(
        zones=tuple(
            Zone(id=z.name, rank=z.rank, x_min=z.x0, y_min=z.y0, x_max=z.x1, y_max=z.y1)
            for z in specification.zones_of(category)
        )
    )


def calibration_for(
    specification: Specification, category: str, *, width_px: int, height_px: int
) -> Calibration:
    """Give the scale of one source image of a part.

    Args:
        specification: The parsed specification.
        category: The part.
        width_px: The source image's width in pixels.
        height_px: The source image's height in pixels.

    Returns:
        The calibration: the specification's imaged width over the image's width.

    Raises:
        JoinError: If the specification declares no calibration for the part.
    """
    declared = specification.calibration(category)
    if declared is None:
        msg = f"the specification declares no calibration for part {category}"
        raise JoinError(msg)
    return Calibration(
        board_width_mm=declared.image_width_mm,
        image_width_px=width_px,
        image_height_px=height_px,
    )


def measure_region(
    labels: NDArray[np.uint16], index: int, calibration: Calibration, zones: ZoneMap
) -> MeasuredRegion:
    """Measure one region of the anomaly model's label image.

    Args:
        labels: The label image at the source image's size: 0 for background,
            a region's index for its pixels.
        index: The region to measure.
        calibration: The source image's scale.
        zones: The part's zones.

    Returns:
        The region, measured in millimetres and placed in its zone.

    Raises:
        JoinError: If the label image is not at the calibration's size, or
            does not hold the region as one connected area.
    """
    height, width = labels.shape
    if (width, height) != (calibration.image_width_px, calibration.image_height_px):
        msg = (
            f"the label image is {width} x {height}, but the source image is "
            f"{calibration.image_width_px} x {calibration.image_height_px}"
        )
        raise JoinError(msg)
    pixels = labels == index
    measured = measure_regions(CalibratedMask(pixels=pixels, calibration=calibration), zones)
    if len(measured) != 1:
        msg = f"region {index} is {len(measured)} connected areas in the label image, not one"
        raise JoinError(msg)
    return measured[0]
