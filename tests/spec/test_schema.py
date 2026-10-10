"""Tests for the clause schema and the specification it belongs to."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from spec_to_inspector.spec.limits import Comparison, Limit, Unit
from spec_to_inspector.spec.schema import (
    ANY_ZONE,
    Specification,
    read_clause_table,
    write_clause_table,
)
from tests.spec.spec_fakes import (
    altered,
    calibration,
    sized_clause,
    specification,
    unconditional_clause,
    zone,
)


def test_a_clause_carries_its_limit_as_a_typed_reject_condition() -> None:
    """The comparison, number and unit of a clause read back as one limit."""
    assert sized_clause().as_limit() == Limit(comparison=Comparison.GT, value=0.5, unit=Unit.MM)
    assert unconditional_clause().as_limit() == Limit(
        comparison=Comparison.UNCONDITIONAL, value=None, unit=None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "4"},
        {"id": "4.1.a"},
        {"id": "4.1.1", "heading_id": "4.2"},
        {"id": "4.1", "heading_id": "4.1.1"},
        {"limit": None},
        {"unit": None},
        {"limit": -1.0},
        {"comparison": Comparison.UNCONDITIONAL},
        {"page": 0},
        {"title": " "},
        {"source_text": ""},
        {"limit_text": ""},
        {"zone": ""},
        {"category": "PCB9"},
        {"defect_class": "Scratch"},
        {"disposition": "scrap"},
    ],
)
def test_a_clause_refuses_fields_that_do_not_agree(changes: dict[str, object]) -> None:
    """A clause whose numbering, limit or names are inconsistent is not built."""
    with pytest.raises(ValidationError):
        altered(sized_clause(), changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"x0": 0.8},
        {"y1": 0.25},
        {"x1": 1.01},
        {"y0": -0.1},
        {"rank": 0},
        {"name": "any"},
        {"name": ""},
    ],
)
def test_a_zone_is_a_proper_rectangle_inside_the_image(changes: dict[str, object]) -> None:
    """Corners are normalised, ordered and inside the unit square; a zone cannot be `any`."""
    with pytest.raises(ValidationError):
        altered(zone(), changes)


def test_a_zone_says_whether_it_contains_a_point() -> None:
    """A point is tested in normalised coordinates, edges included."""
    a = zone()

    assert a.contains(0.5, 0.5)
    assert a.contains(0.25, 0.75)
    assert not a.contains(0.2, 0.5)


def test_a_calibration_turns_pixels_into_millimetres_on_each_axis() -> None:
    """The scale is the imaged size over the pixel count, separately across and down."""
    scale = calibration().mm_per_pixel(width_px=1000, height_px=400)

    assert scale == (0.05, 0.1)


@pytest.mark.parametrize("changes", [{"board_width_mm": 0.0}, {"image_width_mm": 30.0}])
def test_a_calibration_refuses_an_impossible_board(changes: dict[str, object]) -> None:
    """The board has a width, and the image is at least as wide as the board it shows."""
    with pytest.raises(ValidationError):
        altered(calibration(), changes)


def test_a_specification_finds_and_resolves_its_clauses() -> None:
    """Clauses are found by id, by class, and by class and zone."""
    spec = specification()

    assert spec.categories() == ("pcb9",)
    assert spec.defect_classes("pcb9") == ("scratch", "missing")
    assert spec.find("4.1.2") == spec.clauses[1]
    assert spec.find("9.9") is None
    assert [c.id for c in spec.clauses_for("pcb9", "scratch")] == ["4.1.1", "4.1.2"]
    assert spec.clauses_for("pcb9", "dirt") == ()
    assert spec.resolve("pcb9", "scratch", "B") == spec.clauses[1]
    assert spec.resolve("pcb9", "missing", "B") == spec.clauses[2]
    assert spec.resolve("pcb9", "missing", None) == spec.clauses[2]
    assert spec.resolve("pcb9", "scratch", None) is None
    assert spec.resolve("pcb9", "scratch", "Z") is None
    assert spec.resolve("pcb9", "dirt", "A") is None
    assert spec.calibration("pcb9") == spec.calibrations[0]
    assert [z.name for z in spec.zones_of("pcb9")] == ["A", "B"]


def test_zones_come_back_most_critical_first() -> None:
    """The rank orders the zones whatever order they were listed in."""
    spec = specification(zones=(zone("B", 2), zone("A", 1)))

    assert [z.name for z in spec.zones_of("pcb9")] == ["A", "B"]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"clauses": (sized_clause("4.1.1", "A"), sized_clause("4.1.1", "B"))}, "more than once"),
        ({"clauses": (sized_clause("4.1.1", "A"),)}, "zone B"),
        ({"clauses": (sized_clause("4.1.1", "C"),)}, "zone 'C'"),
        (
            {
                "clauses": (
                    sized_clause("4.1.1", "A"),
                    sized_clause("4.1.2", "B"),
                    sized_clause("4.1.3", ANY_ZONE),
                )
            },
            "both",
        ),
        (
            {"clauses": (unconditional_clause("4.2"), unconditional_clause("4.3"))},
            "more than once",
        ),
        ({"calibrations": ()}, "calibration"),
        ({"calibrations": (calibration(), calibration())}, "calibration"),
        ({"zones": (zone("A", 1), zone("A", 2))}, "zone A"),
        ({"zones": (zone("A", 1), zone("B", 1))}, "rank"),
        ({"zones": (zone("A", 1), zone("B", 2), zone("Z", 1, category="pcb8"))}, "pcb8"),
        ({"clauses": ()}, "no clauses"),
        ({"pages": 2}, "page 3"),
    ],
)
def test_a_specification_refuses_a_table_that_cannot_be_judged_against(
    changes: dict[str, object], reason: str
) -> None:
    """Every defect class resolves to exactly one clause in every zone, or the table is refused."""
    with pytest.raises(ValidationError, match=reason):
        altered(specification(), changes)


def test_the_clause_table_round_trips_through_json(tmp_path: Path) -> None:
    """What is written is what is read, and the file ends with a newline."""
    path = tmp_path / "nested" / "spec.clauses.json"
    spec = specification()

    write_clause_table(spec, path)

    assert read_clause_table(path) == spec
    assert path.read_text(encoding="utf-8").endswith("}\n")


def test_the_json_keeps_limits_as_numbers_and_refuses_unknown_fields() -> None:
    """A limit is a JSON number, never prose; a field the schema lacks is an error."""
    spec = specification()
    dumped = spec.model_dump(mode="json")

    assert dumped["schema_version"] == 1
    assert dumped["clauses"][0]["limit"] == 0.5
    assert dumped["clauses"][0]["comparison"] == ">"
    assert dumped["clauses"][0]["unit"] == "mm"
    assert dumped["clauses"][2]["limit"] is None
    with pytest.raises(ValidationError):
        Specification.model_validate(dumped | {"surprise": 1})
