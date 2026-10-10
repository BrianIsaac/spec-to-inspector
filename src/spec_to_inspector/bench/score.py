"""The scorer: the figures of `eval/PROTOCOL.md`, counted from labels and observations.

Nothing here reads a file or asks a model. The labelled set says what is
expected of each anomalous image; an observation says what the pipeline did
with it; every figure is a count of the one against the other, given with its
N and its 95% Wilson score interval.
"""

from collections import Counter
from collections.abc import Callable, Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from spec_to_inspector.bench.labels import ClauseLabel, Region1
from spec_to_inspector.bench.mapping import CLAUSE_MAPPING
from spec_to_inspector.bench.observe import Citation, Observation
from spec_to_inspector.bench.wilson import Proportion, wilson
from spec_to_inspector.judge.disposition import Outcome

Pair = tuple[ClauseLabel, Observation]
Confusion = dict[str, dict[str, dict[str, int]]]
"""Per part, per expected defect type, how often each column was what the judge cited."""


class ScoreError(ValueError):
    """The labels and the observations do not describe the same images."""


class Accuracy(BaseModel):
    """One share, for the parts together and for each part.

    Attributes:
        all: Over the images of every part.
        by_part: Over each part's own images.
    """

    model_config = ConfigDict(frozen=True)

    all: Proportion
    by_part: dict[str, Proportion]


class Headline(BaseModel):
    """The strict figure on the single-defect images, and what stands beside it.

    Attributes:
        strict: Images whose citation on region 1 is the expected heading,
            over every single-defect image; no citation counts as wrong.
        flagged: Single-defect images on which the anomaly model flagged an area.
        on_defect: Single-defect images whose region 1 lies on the labelled defect.
        strict_given_flagged: The strict share over the flagged images only.
        strict_given_on_defect: The strict share over the images whose
            region 1 lies on the labelled defect.
        rows_applied: For the correct citations, how often code applied each
            row of the clause table; `no row` where it applied none.
        region1_outcomes: For the correct citations, what became of region 1:
            `reject`, `accept`, or `needs review: <cause>`.
    """

    model_config = ConfigDict(frozen=True)

    strict: Accuracy
    flagged: Accuracy
    on_defect: Accuracy
    strict_given_flagged: Accuracy
    strict_given_on_defect: Accuracy
    rows_applied: dict[str, int]
    region1_outcomes: dict[str, int]


class Dispositions(BaseModel):
    """What became of a set of boards, and of the areas judged on them.

    Attributes:
        boards: The boards in the set.
        not_flagged: Boards the anomaly model flagged no area on; the
            pipeline accepts them without asking the judge.
        board_outcomes: The outcomes of the flagged boards.
        board_review_causes: The referred boards, by cause.
        board_needs_review: Boards referred, over every board of the set.
        areas: Areas put before the judge on those boards.
        area_outcomes: The areas' outcomes.
        area_review_causes: The referred areas, by cause.
        area_needs_review: Areas referred, over every area judged.
    """

    model_config = ConfigDict(frozen=True)

    boards: int
    not_flagged: int
    board_outcomes: dict[str, int]
    board_review_causes: dict[str, int]
    board_needs_review: Proportion
    areas: int
    area_outcomes: dict[str, int]
    area_review_causes: dict[str, int]
    area_needs_review: Proportion


class FalseAlarms(BaseModel):
    """The good boards of a set: how many were flagged, and what became of those.

    Attributes:
        flagged: Good boards the anomaly model flagged, over every good board.
        rejected: Good boards the pipeline rejected: the false rejects.
        referred: Good boards referred to an engineer.
        accepted_after_judging: Good boards flagged, judged and accepted.
        citations: What the judge cited on region 1 of the flagged good
            boards: a heading id, or why there is none.
        dispositions: The same breakdown as for the anomalous boards.
    """

    model_config = ConfigDict(frozen=True)

    flagged: Proportion
    rejected: Proportion
    referred: Proportion
    accepted_after_judging: Proportion
    citations: dict[str, int]
    dispositions: Dispositions


class GoodBoards(BaseModel):
    """The false alarms, for the parts together and for each part.

    Attributes:
        all: Over the good boards of every part.
        by_part: Over each part's own good boards.
    """

    model_config = ConfigDict(frozen=True)

    all: FalseAlarms
    by_part: dict[str, FalseAlarms]


class Scores(BaseModel):
    """Every counted figure of the protocol.

    Attributes:
        headline: The strict figure on the single-defect images.
        lenient: Multi-defect images whose citation is the heading of any of
            their defect types. Never pooled with the headline.
        per_region: Images whose region 1 lies on exactly one defect type and
            whose citation is that type's heading.
        confusion_single: Over the single-defect images: the expected type
            against the type of the heading cited.
        confusion_region: The same over the images of the per-region figure,
            by the type under region 1.
        class_not_of_heading: Citations on labelled images whose named class
            is not the class of the heading cited.
        anomalous: What became of the anomalous boards and their areas.
        good: The false alarms on the good boards.
        stale_region_truth: Labelled images whose region columns are not what
            this run's region 1 lies on; the per-region figure needs none.
    """

    model_config = ConfigDict(frozen=True)

    headline: Headline
    lenient: Accuracy
    per_region: Accuracy
    confusion_single: Confusion
    confusion_region: Confusion
    class_not_of_heading: int
    anomalous: Dispositions
    good: GoodBoards
    stale_region_truth: list[str]


_TYPE_OF_HEADING = {(row.part, row.heading_id): row.visa_type for row in CLAUSE_MAPPING}


def _ordered(counter: Counter[str]) -> dict[str, int]:
    """Lay counts out most frequent first, ties in the order first seen.

    Args:
        counter: The counts.

    Returns:
        The counts as a plain mapping.
    """
    return dict(counter.most_common())


def _accuracy(pairs: Sequence[Pair], parts: Sequence[str], hit: Callable[[Pair], bool]) -> Accuracy:
    """Count the pairs that satisfy a criterion, together and per part.

    Args:
        pairs: Each label with its observation: the figure's N.
        parts: The parts to give a share for, also where a part has no pair.
        hit: The criterion.

    Returns:
        The share for all pairs and for each part's.
    """
    by_part = {
        part: wilson(
            sum(hit(pair) for pair in pairs if pair[0].part == part),
            sum(pair[0].part == part for pair in pairs),
        )
        for part in parts
    }
    return Accuracy(all=wilson(sum(hit(pair) for pair in pairs), len(pairs)), by_part=by_part)


def _cites(observation: Observation, headings: Iterable[str]) -> bool:
    """Whether an image's citation on region 1 is one of some headings.

    Args:
        observation: The image, as the bench saw it.
        headings: The headings that count.

    Returns:
        True for a citation among them; false for another or for none.
    """
    return observation.citation is Citation.CITED and observation.cited_heading in set(headings)


def _column(observation: Observation) -> str:
    """Name the confusion table's column for an image.

    Args:
        observation: The image, as the bench saw it.

    Returns:
        The VisA type of the heading cited, or why there is no citation.
    """
    if observation.citation is not Citation.CITED or observation.cited_heading is None:
        return observation.citation.value
    cited = (observation.part, observation.cited_heading)
    return _TYPE_OF_HEADING.get(cited, f"heading {observation.cited_heading}")


def _confusion(rows: Iterable[tuple[str, str, Observation]]) -> Confusion:
    """Build a confusion table.

    Args:
        rows: Per image, its part, its expected defect type and what was seen.

    Returns:
        The counts per part, expected type and column.
    """
    counted: dict[str, dict[str, Counter[str]]] = {}
    for part, expected, observation in rows:
        counted.setdefault(part, {}).setdefault(expected, Counter())[_column(observation)] += 1
    return {
        part: {expected: _ordered(columns) for expected, columns in table.items()}
        for part, table in counted.items()
    }


def _dispositions(observations: Sequence[Observation]) -> Dispositions:
    """Count what became of some boards and of the areas judged on them.

    Args:
        observations: The boards.

    Returns:
        The breakdown at both levels.
    """
    flagged = [observation for observation in observations if observation.flagged]
    areas = [area for observation in flagged for area in observation.areas]
    referred = [o for o in flagged if o.outcome is Outcome.NEEDS_REVIEW]
    referred_areas = [area for area in areas if area.outcome is Outcome.NEEDS_REVIEW]
    return Dispositions(
        boards=len(observations),
        not_flagged=len(observations) - len(flagged),
        board_outcomes=_ordered(Counter(o.outcome.value for o in flagged)),
        board_review_causes=_ordered(
            Counter(o.review_cause.value for o in referred if o.review_cause is not None)
        ),
        board_needs_review=wilson(len(referred), len(observations)),
        areas=len(areas),
        area_outcomes=_ordered(Counter(area.outcome.value for area in areas)),
        area_review_causes=_ordered(
            Counter(a.review_cause.value for a in referred_areas if a.review_cause is not None)
        ),
        area_needs_review=wilson(len(referred_areas), len(areas)),
    )


def _false_alarms(good: Sequence[Observation]) -> FalseAlarms:
    """Count the false alarms on some good boards.

    Args:
        good: The good boards.

    Returns:
        How many were flagged, and what became of those.
    """
    flagged = [observation for observation in good if observation.flagged]

    def share(outcome: Outcome) -> Proportion:
        return wilson(sum(o.outcome is outcome for o in flagged), len(good))

    return FalseAlarms(
        flagged=wilson(len(flagged), len(good)),
        rejected=share(Outcome.REJECT),
        referred=share(Outcome.NEEDS_REVIEW),
        accepted_after_judging=share(Outcome.ACCEPT),
        citations=_ordered(
            Counter(
                o.cited_heading
                if o.citation is Citation.CITED and o.cited_heading is not None
                else o.citation.value
                for o in flagged
            )
        ),
        dispositions=_dispositions(good),
    )


def _headline(single: Sequence[Pair], parts: Sequence[str]) -> Headline:
    """Count the strict figure and what stands beside it.

    Args:
        single: The single-defect images, each with its observation.
        parts: The parts.

    Returns:
        The headline.
    """

    def strict(pair: Pair) -> bool:
        return _cites(pair[1], pair[0].expected_headings)

    flagged = [pair for pair in single if pair[1].flagged]
    on_defect = [
        pair for pair in single if pair[0].region1 in (Region1.ONE_TYPE, Region1.SEVERAL_TYPES)
    ]
    correct = [observation for label, observation in single if strict((label, observation))]
    outcomes: Counter[str] = Counter()
    for observation in correct:
        first = observation.areas[0]
        cause = "" if first.review_cause is None else f": {first.review_cause.value}"
        outcomes[f"{first.outcome.value}{cause}"] += 1
    return Headline(
        strict=_accuracy(single, parts, strict),
        flagged=_accuracy(single, parts, lambda pair: pair[1].flagged),
        on_defect=_accuracy(single, parts, lambda pair: pair in on_defect),
        strict_given_flagged=_accuracy(flagged, parts, strict),
        strict_given_on_defect=_accuracy(on_defect, parts, strict),
        rows_applied=_ordered(Counter(o.row_id or "no row" for o in correct)),
        region1_outcomes=_ordered(outcomes),
    )


def _is_stale(label: ClauseLabel, observation: Observation) -> bool:
    """Whether a label's region columns disagree with what the run's region 1 lies on.

    Args:
        label: The image's row of the labelled set.
        observation: The image, as the bench saw it.

    Returns:
        True when the labelled set should be rebuilt from this model's regions.
    """
    if label.region1 is Region1.NO_REGION:
        return observation.flagged
    return observation.region1_types != label.region1_types


def score(labels: Sequence[ClauseLabel], observations: Sequence[Observation]) -> Scores:
    """Count every figure of the protocol.

    Args:
        labels: The labelled set, or the part of it that was run.
        observations: What the bench saw of every image it ran: the labelled
            images and the good boards.

    Returns:
        The figures.

    Raises:
        ScoreError: If a labelled image has no observation, or an image was
            observed twice.
    """
    seen = {observation.key: observation for observation in observations}
    if len(seen) != len(observations):
        msg = "an image was observed twice"
        raise ScoreError(msg)
    missing = [f"{label.part} {label.image_id}" for label in labels if _key(label) not in seen]
    if missing:
        msg = f"the run holds no observation for {', '.join(missing)}"
        raise ScoreError(msg)

    parts = tuple(dict.fromkeys([label.part for label in labels] + [o.part for o in observations]))
    pairs = [(label, seen[_key(label)]) for label in labels]
    single = [pair for pair in pairs if pair[0].single]
    multi = [pair for pair in pairs if not pair[0].single]
    one_type = [pair for pair in pairs if pair[0].region1 is Region1.ONE_TYPE]
    good = [observation for observation in observations if observation.label == "good"]

    return Scores(
        headline=_headline(single, parts),
        lenient=_accuracy(multi, parts, lambda pair: _cites(pair[1], pair[0].expected_headings)),
        per_region=_accuracy(
            one_type, parts, lambda pair: _cites(pair[1], pair[0].region1_headings)
        ),
        confusion_single=_confusion((lb.part, lb.visa_types[0], ob) for lb, ob in single),
        confusion_region=_confusion((lb.part, lb.region1_types[0], ob) for lb, ob in one_type),
        class_not_of_heading=sum(
            ob.citation is Citation.CITED
            and ob.cited_heading is not None
            and _TYPE_OF_HEADING.get((ob.part, ob.cited_heading)) != ob.cited_class
            for _, ob in pairs
        ),
        anomalous=_dispositions([observation for _, observation in pairs]),
        good=GoodBoards(
            all=_false_alarms(good),
            by_part={part: _false_alarms([o for o in good if o.part == part]) for part in parts},
        ),
        stale_region_truth=[
            f"{label.part} {label.image_id}"
            for label, observation in pairs
            if _is_stale(label, observation)
        ],
    )


def _key(label: ClauseLabel) -> tuple[str, str]:
    """Name a labelled image as an observation is named.

    Args:
        label: The image's row of the labelled set.

    Returns:
        The part and the image id.
    """
    return (label.part, label.image_id)
