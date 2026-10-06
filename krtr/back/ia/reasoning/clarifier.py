"""Resolves the turns the matcher is not sure about, by asking the customer.

Exists as the non-deterministic layer's seat (docs/ia-proposal.md §2): today a template
clarifier that offers the candidates and reads option numbers or keywords; in phase 3 an LLM
clarifier behind the same interface reads free-form replies. Either may only resolve to an
intent of the catalog, never answer the question itself. Consumed by `reasoning/resolver.py`.
"""

from abc import ABC, abstractmethod

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.matching.artifacts import MatchKind, MatchResult
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    PendingQuestion,
    QuestionKind,
    Resolution,
    Resolved,
)
from krtr.back.ia.text import first_number


class Clarifier(ABC):
    """Turns doubt into a question, and a reply into a resolution."""

    @abstractmethod
    def ask(self, match: MatchResult) -> Resolution:
        """Builds the question for a message that did not match clearly.

        Args:
            match: The matcher's verdict, `AMBIGUOUS` or `NO_MATCH`.

        Returns:
            Resolution: usually a question; an LLM clarifier may resolve directly.
        """

    @abstractmethod
    def interpret(self, state: ConversationState, text: str, match: MatchResult) -> Resolution:
        """Reads the customer's reply to the pending question.

        Args:
            state: The conversation, with its pending question.
            text: The reply.
            match: The matcher's verdict on the reply itself.

        Returns:
            Resolution: the intent and slots the reply settles, or the question again.
        """


class TemplateClarifier(Clarifier):
    """Offers numbered options and reads the number, a keyword, or a clear new request.

    Exists so the whole clarification flow works without a model (phase 1).
    """

    def __init__(self, actions: ActionRegistry) -> None:
        """Keeps the actions, which extract slot values from replies.

        Args:
            actions: The intent → action registry.
        """
        self._actions = actions

    def ask(self, match: MatchResult) -> Resolution:
        """Offers the candidates on `AMBIGUOUS`, or asks to rephrase on `NO_MATCH`.

        Args:
            match: The matcher's verdict.

        Returns:
            Resolution: the question.
        """
        if match.kind == MatchKind.NO_MATCH:
            return NeedsClarification(question=PendingQuestion(kind=QuestionKind.REPHRASE))
        options = [candidate.intent.value for candidate in match.candidates]
        question = PendingQuestion(kind=QuestionKind.CHOOSE_INTENT, options=options)
        return NeedsClarification(question=question)

    def interpret(self, state: ConversationState, text: str, match: MatchResult) -> Resolution:
        """Reads the reply against the pending question; a clear new request wins otherwise.

        Args:
            state: The conversation, with its pending question.
            text: The reply.
            match: The matcher's verdict on the reply itself.

        Returns:
            Resolution: what the reply settles, a new request, or the question again.
        """
        question = state.pending
        answer = self._answer(question, text) if question else None
        if answer is not None:
            return answer
        if match.best_intent is not None:
            return Resolved(intent=match.best_intent)
        if question is None or question.kind == QuestionKind.REPHRASE:
            return self.ask(match)
        return NeedsClarification(question=question)

    def _answer(self, question: PendingQuestion, text: str) -> Resolved | None:
        """Reads the reply as an answer to one kind of question.

        Args:
            question: The pending question.
            text: The reply.

        Returns:
            Resolved | None: the settled intent and slots, or None if the reply does not answer.
        """
        if question.kind == QuestionKind.CHOOSE_INTENT:
            chosen = _pick_option(text, question.options)
            return Resolved(intent=Intent(chosen)) if chosen else None
        if question.intent is None or question.slot is None:
            return None
        value = self._slot_value(question, text)
        if value is None:
            return None
        return Resolved(intent=question.intent, slots={**question.collected, question.slot: value})

    def _slot_value(self, question: PendingQuestion, text: str) -> str | None:
        """Reads a slot's value from a reply: an option number first, then the action's rules.

        Args:
            question: The pending slot question, with its intent and slot.
            text: The reply.

        Returns:
            str | None: the slot's value, or None if the reply does not give it.
        """
        picked = _pick_option(text, question.options)
        if picked:
            return picked
        return self._actions.get(question.intent).extract_slots(text).get(question.slot)


def _pick_option(text: str, options: list[str]) -> str | None:
    """Reads "2" or "la 2" as the second option.

    Args:
        text: The reply.
        options: The options offered, in the order they were numbered (from 1).

    Returns:
        str | None: the chosen option, or None if the reply names no offered number.
    """
    number = first_number(text)
    if number is None or not 1 <= number <= len(options):
        return None
    return options[number - 1]
