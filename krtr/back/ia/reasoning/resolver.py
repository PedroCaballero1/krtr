"""Turns a message and the matcher's verdict into one resolution: answer, ask, or escalate.

Exists as the deterministic core of every turn: a clear match with its slots goes straight to
an action; doubt goes to the clarifier; a known intent with a missing slot becomes a question
for that slot; too many questions in a row escalate the case (G19, G20). Consumed by
`engine/engine.py`.
"""

import logging

from krtr.back.ia.config import IaConfig
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.matching.artifacts import MatchResult
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

    def resolve(self, state: ConversationState, text: str, match: MatchResult) -> Resolution:
        """Resolves one turn.

        Args:
            state: The conversation so far.
            text: The customer's message.
            match: The matcher's verdict on the message.

        Returns:
            Resolution: a complete `Resolved`, a question, or an escalation.
        """
        if state.pending is not None:
            resolution = self._clarifier.interpret(state, text, match)
        elif match.best_intent is not None:
            resolution = Resolved(intent=match.best_intent)
        else:
            resolution = self._clarifier.ask(match)
        if isinstance(resolution, Resolved):
            resolution = self._complete_slots(resolution, text)
        return self._apply_limit(state, resolution)

    def _complete_slots(self, resolution: Resolved, text: str) -> Resolved | NeedsClarification:
        """Adds the slots the message states and asks for the first one still missing.

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
