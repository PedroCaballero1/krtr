"""Confirms guard flags with the LLM, reading the flagged message in its conversation.

Exists so the guardrails stay free of I/O: they pass the conversation's state, and this
confirmer loads the case's history once per flagged turn, however many flags it carries.
Implements `guardrails/policy.GuardConfirmer`; built by `engine/factory.py`.
"""

from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.security.oidc.artifacts import InterfaceLanguage


class LlmGuardConfirmer:
    """Asks the LLM to classify a flagged message, with the case's history as context.

    Exists so an angry reply to a banking problem raised earlier is read as banking, and the
    case isn't closed on a real customer.
    """

    def __init__(self, tasks: LlmTasks, history: ConversationHistory) -> None:
        """Keeps the LLM tasks and the history loader.

        Args:
            tasks: The closed LLM tasks.
            history: Loads the case's earlier messages.
        """
        self._tasks = tasks
        self._history = history

    def confirm_first(
        self,
        state: ConversationState,
        labels: list[GuardLabel],
        reply: str,
        language: InterfaceLanguage,
    ) -> GuardLabel | None:
        """Returns the first flag the LLM confirms, loading the history once.

        Args:
            state: The conversation, which identifies the case.
            labels: The closing flags raised on the message, in order.
            reply: The flagged message.
            language: The customer's language.

        Returns:
            GuardLabel | None: the first confirmed flag, or None if none is confirmed.
        """
        transcript = self._history.load(state)
        for label in labels:
            if self._tasks.confirm_guard(label, reply, transcript, language):
                return label
        return None
