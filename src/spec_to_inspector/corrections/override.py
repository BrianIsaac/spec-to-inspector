"""Making an override: the judge's decision on disk, and the engineer's word against it.

The judged half of an override is read from the image's `decision.json`, never
typed in: the class and the clause the model named for that region, the
outcome code gave it, and the model's own line. The corrected half is checked
against the clause table of the board's own part, so the store holds no clause
that does not exist and no class under another's clause. The command line's
`correct` verb and the console's form both end in `record_override`.
"""

from pathlib import Path

from pydantic import ValidationError

from spec_to_inspector.corrections.store import Correction, CorrectionStore, Override
from spec_to_inspector.judge.decision import Decision, RegionDecision
from spec_to_inspector.judge.inspect import DECISION_NAME, load_decision, write_decision
from spec_to_inspector.spec.schema import Specification


class OverrideError(ValueError):
    """An override cannot be made as asked; the message says why."""


def _region(decision: Decision, region_index: int | None) -> RegionDecision:
    """Find the judged region an override is about.

    Args:
        decision: The image's decision.
        region_index: The region named, or None for the one the decision
            rests on.

    Returns:
        The region's decision.

    Raises:
        OverrideError: If the image has no judged region, the named region
            was not judged, or none is named and the decision rests on none.
    """
    if not decision.regions:
        msg = (
            f"no flagged area of {decision.image_id} was judged, so there is no judgement "
            "to override"
        )
        raise OverrideError(msg)
    judged = ", ".join(str(region.index) for region in decision.regions)
    index = region_index
    if index is None:
        index = decision.deciding_region
    if index is None and len(decision.regions) == 1:
        index = decision.regions[0].index
    if index is None:
        msg = (
            f"the decision on {decision.image_id} rests on no single region; name one of the "
            f"regions judged: {judged}"
        )
        raise OverrideError(msg)
    found = next((region for region in decision.regions if region.index == index), None)
    if found is None:
        msg = (
            f"region {index} of {decision.image_id} was not judged; the regions judged are {judged}"
        )
        raise OverrideError(msg)
    return found


def _citation(
    specification: Specification, category: str, clause_id: str | None, defect_class: str | None
) -> tuple[str | None, str | None]:
    """Check the engineer's class and clause against the part's own table.

    Args:
        specification: The parsed specification.
        category: The part the board is.
        clause_id: The clause the engineer cites, as a numbered heading or one
            of its rows; None to take it from the class.
        defect_class: The class the engineer names; None to take it from the
            clause.

    Returns:
        The class and its numbered heading, or None for both when the
        engineer gave neither: no clause applies.

    Raises:
        OverrideError: If the part has no such clause or class, or the class
            is not the clause's.
    """
    if clause_id is None and defect_class is None:
        return None, None
    headings: dict[str, str] = {}
    rows: dict[str, str] = {}
    for clause in specification.clauses:
        if clause.category == category:
            headings.setdefault(clause.heading_id, clause.defect_class)
            rows[clause.id] = clause.heading_id
    if clause_id is None:
        cited = [heading for heading, held in headings.items() if held == defect_class]
        if len(cited) != 1:
            classes = ", ".join(dict.fromkeys(headings.values()))
            msg = (
                f"part {category} has no defect class '{defect_class}'; its classes are {classes}"
                if not cited
                else f"'{defect_class}' has more than one clause in part {category}: "
                f"{', '.join(cited)}; name the clause"
            )
            raise OverrideError(msg)
        return defect_class, cited[0]
    heading = clause_id.strip()
    heading = heading if heading in headings else rows.get(heading)
    if heading is None:
        msg = f"part {category} has no clause {clause_id}; its clauses are {', '.join(headings)}"
        raise OverrideError(msg)
    if defect_class is not None and defect_class != headings[heading]:
        msg = f"clause {heading} is for '{headings[heading]}', not '{defect_class}'"
        raise OverrideError(msg)
    return headings[heading], heading


def build_override(
    decision: Decision,
    specification: Specification,
    directory: Path,
    *,
    region_index: int | None = None,
    clause_id: str | None = None,
    defect_class: str | None = None,
    note: str = "",
) -> Override:
    """Make the override of one judged region from its decision.

    Args:
        decision: The image's decision, as judged.
        specification: The parsed specification the board was judged against.
        directory: The image's directory in its run, for the crop's path.
        region_index: The region overridden; the one the decision rests on,
            if None.
        clause_id: The clause the engineer cites: a numbered heading, or one
            of its rows, which stands for the heading.
        defect_class: The class the engineer names. One of the two is enough;
            with neither, the engineer says that no clause applies.
        note: The engineer's note.

    Returns:
        The override, not yet stored.

    Raises:
        OverrideError: If the region was not judged, the citation is not in
            the part's table, the override repeats the judge's answer, or a
            field is malformed.
    """
    region = _region(decision, region_index)
    corrected_class, corrected_clause = _citation(
        specification, decision.category, clause_id, defect_class
    )
    answer = region.answer
    try:
        return Override(
            category=decision.category,
            image_id=decision.image_id,
            region_index=region.index,
            crop_path=None if region.crop is None else str((directory / region.crop).resolve()),
            judged_class=None if answer is None else answer.defect_class,
            judged_clause=None if answer is None else answer.clause_id,
            judged_outcome=region.outcome,
            judged_reason=None if answer is None else answer.reason,
            corrected_class=corrected_class,
            corrected_clause=corrected_clause,
            note=note,
        )
    except ValidationError as error:
        problems = "; ".join(
            ": ".join(
                part
                for part in (
                    ".".join(str(place) for place in issue["loc"]),
                    issue["msg"].removeprefix("Value error, "),
                )
                if part
            )
            for issue in error.errors()
        )
        raise OverrideError(problems) from error


def record_override(
    store: CorrectionStore,
    directory: Path,
    specification: Specification,
    *,
    region_index: int | None = None,
    clause_id: str | None = None,
    defect_class: str | None = None,
    note: str = "",
) -> Correction:
    """Record an engineer's override of an image's decision, and flag the decision.

    The row goes into the store first; then the image's `decision.json` is
    written again with its "corrected" flag saying it was overridden, and
    nothing else changed.

    Args:
        store: The corrections store.
        directory: The image's directory in its run, holding `decision.json`.
        specification: The parsed specification the board was judged against.
        region_index: The region overridden; the one the decision rests on,
            if None.
        clause_id: The clause the engineer cites, as a heading or a row.
        defect_class: The class the engineer names. With neither this nor the
            clause, the engineer says that no clause applies.
        note: The engineer's note.

    Returns:
        The correction as stored.

    Raises:
        OverrideError: If the image has no decision, or the override cannot
            be made from it as asked.
        spec_to_inspector.corrections.store.StoreError: If the store's file
            cannot be used.
    """
    try:
        decision = load_decision(directory)
    except (OSError, ValueError) as error:
        msg = (
            f"{directory} holds no decision; judge it first with `spec-to-inspector inspect` "
            f"(no readable {DECISION_NAME}: {error})"
        )
        raise OverrideError(msg) from error
    override = build_override(
        decision,
        specification,
        directory,
        region_index=region_index,
        clause_id=clause_id,
        defect_class=defect_class,
        note=note,
    )
    kept = store.record(override)
    flagged = decision.corrected.model_copy(update={"overridden": True})
    write_decision(directory, decision.model_copy(update={"corrected": flagged}))
    return kept
