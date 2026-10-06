"""Turns a message and the matcher's verdict into one resolution: answer, ask, or escalate.

Exists as the deterministic core of every turn:
- a clear match with its slots goes straight to an action;
- a banking request the agent can't answer goes straight to a person;
- doubt goes to the clarifier;
- a known intent with a missing slot becomes a question for that slot;
- too many questions in a row escalate the case (G19, G20). Consumed by
`engine/engine.py`.
"""

import logging

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.matching.artifacts import MatchKind, MatchResult
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    Escalated,
    EscalationReason,
    NeedsClarification,
    PendingQuestion,
    QuestionKind,
    Resolution,
    Resolved,
)
from krtr.back.ia.reasoning.clarifier import Clarifier
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)


class TurnResolver:
    """Decides what a turn does, before anything is executed or phrased.

    Exists so the engine only applies a resolution and never decides one. Built by
    `engine/factory.py`.
    """

    def __init__(self, actions: ActionRegistry, clarifier: Clarifier, config: IaConfig) -> None:
        """Keeps the actions, the clarifier and the conversation limits.

        Args:
            actions: The intent → action registry.
            clarifier: Resolves the doubtful turns.
            config: The clarification limit.
        """
        self._actions = actions
        self._clarifier = clarifier
        self._config = config

    def resolve(
        self,
        state: ConversationState,
        text: str,
        match: MatchResult,
        language: InterfaceLanguage,
    ) -> Resolution:
        """Resolves one turn.

        Args:
            state: The conversation so far.
            text: The customer's message.
            match: The matcher's verdict on the message.
            language: The turn's language, for the LLM's prompts.

        Returns:
            Resolution: a complete `Resolved`, a question, or an escalation.
        """
        if state.pending is not None:
            resolution = self._clarifier.interpret(state, text, match, language)
            if not isinstance(resolution, Resolved) and _is_unsupported(match):
                return self._escalate_unsupported(state)
        elif _is_unsupported(match):
            return self._escalate_unsupported(state)
        elif match.best_intent is not None:
            resolution = Resolved(intent=match.best_intent)
        else:
            resolution = self._clarifier.ask(match)
        if isinstance(resolution, Resolved):
            resolution = self._complete_slots(resolution, text)
        return self._apply_limit(state, resolution)

    def _escalate_unsupported(self, state: ConversationState) -> Escalated:
        """Hands a banking request the agent can't answer to a person (G20).

        Args:
            state: The conversation.

        Returns:
            Escalated: with the `UNSUPPORTED_REQUEST` reason.
        """
        logger.info("Unsupported request in incident %s: escalating", state.incident_id)
        return Escalated(reason=EscalationReason.UNSUPPORTED_REQUEST)

    def _complete_slots(self, resolution: Resolved, text: str) -> Resolved | NeedsClarification:
        """Adds the slots the message states and asks for the first one still missing.

        Only the rules fill slots here. The LLM is not asked to guess one from the first
        message: measured, it picked a product for "¿Cuál es mi saldo?", which names none. It
        only reads the customer's reply once the question has been asked.

        Args:
            resolution: The intent and the slots gathered so far.
            text: The customer's message.

        Returns:
            Resolved | NeedsClarification: the complete resolution, or the next slot question.
        """
        action = self._actions.get(resolution.intent)
        slots = {**action.extract_slots(text), **resolution.slots}
        missing = action.missing_slots(slots)
        if not missing:
            return Resolved(intent=resolution.intent, slots=slots)
        options = action.slot_options(missing[0])
        kind = QuestionKind.CHOOSE_OPTION if options else QuestionKind.PROVIDE_SLOT
        question = PendingQuestion(
            kind=kind, intent=resolution.intent, slot=missing[0], options=options, collected=slots
        )
        return NeedsClarification(question=question)

    def _apply_limit(self, state: ConversationState, resolution: Resolution) -> Resolution:
        """Escalates instead of asking once the clarification limit is reached.

        Args:
            state: The conversation, with how many questions in a row were asked.
            resolution: The resolution so far.

        Returns:
            Resolution: the same resolution, or `Escalated` past the limit.
        """
        over_limit = state.clarification_attempts >= self._config.max_clarification_turns
        if isinstance(resolution, NeedsClarification) and over_limit:
            logger.info("Clarification limit reached for incident %s", state.incident_id)
            return Escalated(reason=EscalationReason.CLARIFICATION_LIMIT)
        return resolution


def _is_unsupported(match: MatchResult) -> bool:
    """Tells whether a message is a banking request the agent can't answer (G20).

    Such a message goes straight to a person: asking to rephrase would only delay it.

    Args:
        match: The matcher's verdict.

    Returns:
        bool: True when no intent matched, `unsupported` is flagged, and it is the best label.
    """
    return (
        match.kind != MatchKind.MATCHED
        and GuardLabel.UNSUPPORTED in match.guard_flags
        and match.top_label == GuardLabel.UNSUPPORTED
    )
