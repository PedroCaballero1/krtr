"""Reads free-form replies the template clarifier can't, by asking the LLM to choose an option.

Exists as the second link of the clarifier chain: the template clarifier (numbers, keywords, a
clear new request) answers first; only when it would repeat the question does the LLM read the
reply, read in the context of the case's earlier messages, and only against the options that
were offered. A slot value it proposes is kept only if the action's own rules accept it. Built
by `engine/factory.py` when an LLM is selected.
"""

import logging

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.matching.artifacts import MatchResult
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    PendingQuestion,
    QuestionKind,
    Resolution,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import Clarifier, TemplateClarifier
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

INTENT_SUBJECT = "request"  # What a "choose an intent" question asks about, for the prompt.


class LlmClarifier(Clarifier):
    """The template clarifier first, then the LLM for the replies it can't read.

    Exists so the LLM is only called on the doubtful replies, and its answer is always one of
    the options offered, or a value written in the reply.
    """

    def __init__(
        self,
        template: TemplateClarifier,
        tasks: LlmTasks,
        actions: ActionRegistry,
        history: ConversationHistory,
    ) -> None:
        """Keeps both links of the chain, the actions that validate slot values and the history.

        Args:
            template: The deterministic clarifier, tried first.
            tasks: The closed LLM tasks.
            actions: The intent → action registry; its rules accept or reject the LLM's values.
            history: Loads the case's earlier messages, only when the LLM is asked.
        """
        self._template = template
        self._tasks = tasks
        self._actions = actions
        self._history = history

    def ask(self, match: MatchResult) -> Resolution:
        """Builds the question exactly as the template clarifier does.

        Args:
            match: The matcher's verdict.

        Returns:
            Resolution: the question.
        """
        return self._template.ask(match)

    def interpret(
        self,
        state: ConversationState,
        text: str,
        match: MatchResult,
        language: InterfaceLanguage,
    ) -> Resolution:
        """Reads the reply with the template clarifier, and with the LLM if it would re-ask.

        Args:
            state: The conversation, with its pending question.
            text: The reply.
            match: The matcher's verdict on the reply itself.
            language: The turn's language.

        Returns:
            Resolution: what the reply settles, or the template clarifier's answer.
        """
        resolution = self._template.interpret(state, text, match, language)
        question = state.pending
        repeats = isinstance(resolution, NeedsClarification) and resolution.question == question
        if not repeats or question is None or question.kind == QuestionKind.REPHRASE:
            return resolution
        answer = self._read_with_llm(state, question, text, language)
        if answer is None:
            return resolution
        logger.info("The LLM read the reply for incident %s", state.incident_id)
        return answer

    def _read_with_llm(
        self,
        state: ConversationState,
        question: PendingQuestion,
        text: str,
        language: InterfaceLanguage,
    ) -> Resolved | None:
        """Asks the LLM for the option (or the slot value) the reply gives, in context.

        Args:
            state: The conversation, which identifies the case whose history is loaded.
            question: The pending question.
            text: The reply.
            language: The turn's language.

        Returns:
            Resolved | None: the settled intent and slots, or None if the LLM sees no answer.
        """
        transcript = self._history.load(state)
        if question.kind == QuestionKind.CHOOSE_INTENT:
            choice = self._tasks.choose_option(
                INTENT_SUBJECT, question.options, text, transcript, language
            )
            return Resolved(intent=Intent(choice)) if choice else None
        if question.intent is None or question.slot is None:
            return None
        proposed = self._tasks.fill_slot(
            question.slot, question.options, text, transcript, language
        )
        action = self._actions.get(question.intent)
        value = action.validate_slot(question.slot, proposed) if proposed else None
        if value is None:
            return None
        return Resolved(intent=question.intent, slots={**question.collected, question.slot: value})
