"""A small valid specification, built in code, for tests that need one."""

from collections.abc import Mapping

from pydantic import BaseModel

from spec_to_inspector.spec.limits import Comparison, Unit
from spec_to_inspector.spec.schema import (
    ANY_ZONE,
    Calibration,
    Clause,
    Disposition,
    Specification,
    Zone,
)


def altered[M: BaseModel](model: M, changes: Mapping[str, object]) -> M:
    """Rebuild a model with some fields replaced, validating it again.

    Args:
        model: A valid model.
        changes: The fields to replace.

    Returns:
        The rebuilt model.

    Raises:
        pydantic.ValidationError: If the changed model is not valid.
    """
    return type(model).model_validate(dict(model) | dict(changes))


def calibration(**changes: object) -> Calibration:
    """Build the calibration of the fake part, with any field replaced.

    Returns:
        A calibration for category `pcb9`.
    """
    fields: dict[str, object] = {
        "category": "pcb9",
        "board_width_mm": 40.0,
        "image_width_mm": 50.0,
        "image_height_mm": 40.0,
        "page": 2,
    }
    return Calibration.model_validate(fields | changes)


def zone(name: str = "A", rank: int = 1, **changes: object) -> Zone:
    """Build a zone of the fake part, with any field replaced.

    Returns:
        A zone of category `pcb9`.
    """
    fields: dict[str, object] = {
        "category": "pcb9",
        "name": name,
        "title": f"Zone {name} of the fake board",
        "rank": rank,
        "x0": 0.25,
        "y0": 0.25,
        "x1": 0.75,
        "y1": 0.75,
        "page": 2,
    }
    return Zone.model_validate(fields | changes)


def sized_clause(clause_id: str = "4.1.1", zone_name: str = "A", **changes: object) -> Clause:
    """Build a clause with a size limit in one zone, with any field replaced.

    Returns:
        A scratch clause of category `pcb9`.
    """
    fields: dict[str, object] = {
        "id": clause_id,
        "heading_id": "4.1",
        "title": "Scratch",
        "category": "pcb9",
        "defect_class": "scratch",
        "zone": zone_name,
        "comparison": Comparison.GT,
        "limit": 0.5,
        "unit": Unit.MM,
        "disposition": Disposition.REJECT,
        "page": 3,
        "source_text": "A scratch longer than the limit of its zone is rejected.",
        "limit_text": "0.5 mm max",
    }
    return Clause.model_validate(fields | changes)


def unconditional_clause(clause_id: str = "4.2", **changes: object) -> Clause:
    """Build a clause that rejects at any size in any zone, with any field replaced.

    Returns:
        A missing-component clause of category `pcb9`.
    """
    fields: dict[str, object] = {
        "id": clause_id,
        "heading_id": clause_id,
        "title": "Missing component",
        "category": "pcb9",
        "defect_class": "missing",
        "zone": ANY_ZONE,
        "comparison": Comparison.UNCONDITIONAL,
        "limit": None,
        "unit": None,
        "disposition": Disposition.REJECT,
        "page": 3,
        "source_text": "A missing component is rejected.",
        "limit_text": "Not permitted",
    }
    return Clause.model_validate(fields | changes)


def specification(**changes: object) -> Specification:
    """Build a two-zone, three-clause specification, with any field replaced.

    Returns:
        A valid specification of one part, `pcb9`.
    """
    fields: dict[str, object] = {
        "title": "Fake workmanship specification",
        "notice": "Written for a test.",
        "pages": 3,
        "calibrations": (calibration(),),
        "zones": (
            zone("A", 1),
            zone("B", 2, x0=0.0, y0=0.0, x1=1.0, y1=1.0),
        ),
        "clauses": (
            sized_clause("4.1.1", "A"),
            sized_clause("4.1.2", "B", limit=1.0, limit_text="1.0 mm max"),
            unconditional_clause("4.2"),
        ),
    }
    return Specification.model_validate(fields | changes)
