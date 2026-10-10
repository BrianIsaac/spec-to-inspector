"""Tests for the join of the specification, the anomaly regions and the measurement."""

import numpy as np
import pytest

from spec_to_inspector.judge import disposition
from spec_to_inspector.judge.join import (
    JoinError,
    calibration_for,
    measure_region,
    rule_clause,
    zone_map_for,
)
from spec_to_inspector.spec.schema import Disposition
from tests.spec.spec_fakes import sized_clause, specification, unconditional_clause


def test_a_sized_clause_becomes_the_rules_clause_field_for_field() -> None:
    """The limit, the unit and the comparison cross unchanged; the zone keeps its letter."""
    clause = rule_clause(sized_clause("4.1.2", "B", limit=1.0))

    assert clause == disposition.Clause(
        id="4.1.2",
        defect_class="scratch",
        zone="B",
        limit=1.0,
        unit="mm",
        comparison=disposition.Comparison.GREATER,
        disposition=disposition.Outcome.REJECT,
    )


def test_a_clause_for_any_zone_has_no_zone_in_the_rule() -> None:
    """The specification writes `any`; the rule's word for it is None."""
    clause = rule_clause(unconditional_clause("4.2"))

    assert clause.zone is None
    assert clause.limit is None
    assert clause.unit is None
    assert clause.comparison is disposition.Comparison.UNCONDITIONAL
    assert clause.disposition is disposition.Outcome.REJECT


def test_a_clause_that_refers_for_review_is_compared_like_a_reject() -> None:
    """The rule finds whether the condition holds; what follows is the judge's to word."""
    clause = rule_clause(sized_clause(disposition=Disposition.REVIEW))

    assert clause.disposition is disposition.Outcome.REJECT


def test_the_zone_map_is_the_parts_zones_with_their_ranks() -> None:
    """Names, ranks and edges cross unchanged, for the part asked and no other."""
    zones = zone_map_for(specification(), "pcb9")

    assert [(z.id, z.rank, z.x_min, z.y_min, z.x_max, z.y_max) for z in zones.strictest_first] == [
        ("A", 1, 0.25, 0.25, 0.75, 0.75),
        ("B", 2, 0.0, 0.0, 1.0, 1.0),
    ]
    assert zone_map_for(specification(), "pcb1").zones == ()


def test_the_scale_comes_from_the_imaged_width_not_the_board_width() -> None:
    """The board does not fill the frame, so the imaged width is what the pixels span."""
    calibration = calibration_for(specification(), "pcb9", width_px=1000, height_px=800)

    assert calibration.board_width_mm == 50.0
    assert calibration.image_width_px == 1000
    assert calibration.image_height_px == 800
    assert calibration.mm_per_px == 0.05


def test_a_part_without_a_calibration_cannot_be_measured() -> None:
    """A board the specification does not cover has no scale, and the error says so."""
    with pytest.raises(JoinError, match="pcb1"):
        calibration_for(specification(), "pcb1", width_px=1000, height_px=800)


def _labels() -> np.ndarray[tuple[int, int], np.dtype[np.uint16]]:
    labels = np.zeros((800, 1000), dtype=np.uint16)
    labels[400:406, 300:330] = 1  # a 30 by 6 bar inside zone A
    labels[40:60, 900:910] = 2  # a 10 by 20 bar in zone B only
    return labels


def test_one_region_of_the_label_image_is_measured_in_millimetres() -> None:
    """Region k of the anomaly model's label image comes back as one measured region."""
    spec = specification()
    calibration = calibration_for(spec, "pcb9", width_px=1000, height_px=800)
    zones = zone_map_for(spec, "pcb9")

    first = measure_region(_labels(), 1, calibration, zones)
    second = measure_region(_labels(), 2, calibration, zones)

    assert first.longest_extent_mm == 30 * 0.05
    assert first.shortest_extent_mm == 6 * 0.05
    assert first.area_px == 180
    assert first.zone == "A"
    assert first.bbox_px == (300, 400, 330, 406)
    assert second.longest_extent_mm == 20 * 0.05
    assert second.zone == "B"


def test_a_region_the_label_image_does_not_hold_is_an_error() -> None:
    """A sidecar that names a region its label image lacks is reported, not measured as nothing."""
    spec = specification()
    calibration = calibration_for(spec, "pcb9", width_px=1000, height_px=800)

    with pytest.raises(JoinError, match="region 3"):
        measure_region(_labels(), 3, calibration, zone_map_for(spec, "pcb9"))


def test_a_region_in_two_pieces_is_an_error() -> None:
    """One region is one connected area; anything else is not the anomaly model's output."""
    labels = _labels()
    labels[700:705, 100:105] = 1
    spec = specification()
    calibration = calibration_for(spec, "pcb9", width_px=1000, height_px=800)

    with pytest.raises(JoinError, match="2 connected areas"):
        measure_region(labels, 1, calibration, zone_map_for(spec, "pcb9"))


def test_a_label_image_of_another_size_than_the_source_is_an_error() -> None:
    """The label image is at the source's size, and a calibration for another size is refused."""
    spec = specification()
    calibration = calibration_for(spec, "pcb9", width_px=500, height_px=400)

    with pytest.raises(JoinError, match="1000 x 800"):
        measure_region(_labels(), 1, calibration, zone_map_for(spec, "pcb9"))
