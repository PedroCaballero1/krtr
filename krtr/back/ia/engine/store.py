"""Keeps each conversation's state between turns.

Exists so the engine loads and saves state through a protocol, and the table that will hold
it (open question Q5) can replace the in-memory store without touching the engine. State is
keyed by customer *and* incident, so one customer can never load another's conversation.
"""

from typing import Protocol

from krtr.back.ia.reasoning.artifacts import ConversationState


class ConversationStateStore(Protocol):
    """Loads and saves conversation state. Consumed by `engine/engine.py`."""

    def load(self, customer_id: str, incident_id: str) -> ConversationState:
        """Returns the conversation's state, or a fresh one.

        Args:
            customer_id: The session's customer.
            incident_id: The case.

        Returns:
            ConversationState: the saved state, or a new empty one.
        """
        ...

    def save(self, state: ConversationState) -> None:
        """Saves the conversation's state.

        Args:
            state: The state after the turn.

        Returns:
            None.
        """
        ...


class InMemoryConversationStateStore:
    """Keeps state in a dictionary for the life of the process.

    Exists for the `krtr back ia` CLI and the tests.
    """

    def __init__(self) -> None:
        """Starts with no conversations."""
        self._states: dict[tuple[str, str], ConversationState] = {}

    def load(self, customer_id: str, incident_id: str) -> ConversationState:
        """Returns a copy of the conversation's state, or a fresh one.

        Args:
            customer_id: The session's customer.
            incident_id: The case.

        Returns:
            ConversationState: the saved state, or a new empty one.
        """
        saved = self._states.get((customer_id, incident_id))
        if saved is None:
            return ConversationState(incident_id=incident_id, customer_id=customer_id)
        return saved.model_copy(deep=True)

    def save(self, state: ConversationState) -> None:
        """Saves a copy of the conversation's state.

        Args:
            state: The state after the turn.

        Returns:
            None.
        """
        self._states[(state.customer_id, state.incident_id)] = state.model_copy(deep=True)
