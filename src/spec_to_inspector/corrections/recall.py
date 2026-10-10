"""Recall into the prompt: the store's corrections as the lines the judge is shown.

Two strategies, chosen by a setting:

- by part: the part's most recent corrections stand in every prompt of a
  batch. One question per region, and the lines are part of the prefix the
  server caches across the batch;
- by answer: the judge is asked first with an empty slot, and only if the
  store holds corrections made where it gave that same answer on that part
  before is it asked again, with those in the slot. The lines are then about
  the mistake it has just made, at the cost of a second question.
"""

from enum import StrEnum
from typing import TypedDict

from spec_to_inspector.corrections.render import render_correction
from spec_to_inspector.corrections.store import MAX_RECALL, CorrectionStore
from spec_to_inspector.judge.answer import JudgeAnswer
from spec_to_inspector.judge.inspect import AnswerRecall, Overridden, Recall


class RecallStrategy(StrEnum):
    """When the store's corrections are put before the judge."""

    PART = "part"
    ANSWER = "answer"


class JudgeOptions(TypedDict):
    """The corrections' share of `judge_image`'s and `judge_run`'s keyword arguments.

    Attributes:
        recall: Recall by part, or None.
        recall_on_answer: Recall on the judge's answer, or None.
        overridden: Whether an image was itself overridden.
    """

    recall: Recall | None
    recall_on_answer: AnswerRecall | None
    overridden: Overridden | None


class StoreRecall:
    """The store's corrections, rendered for the prompt's slot."""

    def __init__(self, store: CorrectionStore, *, limit: int = MAX_RECALL) -> None:
        """Bind the recall to a store.

        Args:
            store: The corrections store.
            limit: The most corrections to show at once; the slot holds three.
        """
        self._store = store
        self._limit = limit

    def for_part(self, category: str) -> tuple[str, ...]:
        """Give the part's most recent corrections, in words.

        Args:
            category: The part.

        Returns:
            At most three lines, most recent first; none from an empty store.
        """
        recalled = self._store.recall_for_part(category, limit=self._limit)
        return tuple(render_correction(correction) for correction in recalled)

    def for_answer(self, category: str, answer: JudgeAnswer) -> tuple[str, ...]:
        """Give the corrections made where the judge gave this answer before, in words.

        Args:
            category: The part.
            answer: The judge's answer to the region in hand.

        Returns:
            At most three lines, most recent first; none if the answer was
            never corrected on this part.
        """
        recalled = self._store.recall_for_answer(
            category, answer.defect_class, answer.clause_id, limit=self._limit
        )
        return tuple(render_correction(correction) for correction in recalled)


def judge_options(
    store: CorrectionStore, strategy: RecallStrategy, *, in_prompt: bool = True
) -> JudgeOptions:
    """Give the judge its corrections from a store, under one strategy.

    Args:
        store: The corrections store; one that does not exist is empty.
        strategy: Recall by part, or on the judge's answer.
        in_prompt: Whether corrections are shown to the judge at all. Off,
            the decision's flag still says whether an image was overridden.

    Returns:
        The keyword arguments for `judge_image` or `judge_run`.
    """
    recalls = StoreRecall(store)
    return JudgeOptions(
        recall=recalls.for_part if in_prompt and strategy is RecallStrategy.PART else None,
        recall_on_answer=(
            recalls.for_answer if in_prompt and strategy is RecallStrategy.ANSWER else None
        ),
        overridden=store.overridden,
    )
