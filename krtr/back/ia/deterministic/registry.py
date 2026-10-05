"""Maps each intent to the one action that answers it.

Exists so the resolver finds an intent's action in one place, and a missing or duplicated
action is caught when the engine is built rather than in the middle of a conversation.
Consumed by `reasoning/resolver.py` and `engine/factory.py`.
"""

from krtr.back.ia.deterministic.base import DeterministicAction
from krtr.back.ia.deterministic.intents import Intent


class ActionRegistry:
    """The intent → action lookup.

    Exists so every member of `Intent` is guaranteed an action. Built by `engine/factory.py`.
    """

    def __init__(self, actions: list[DeterministicAction]) -> None:
        """Indexes the actions by intent, failing fast on gaps or duplicates.

        Args:
            actions: One action per member of `Intent`.

        Raises:
            ValueError: if two actions share an intent or an intent has no action.
        """
        self._actions: dict[Intent, DeterministicAction] = {}
        for action in actions:
            if action.intent in self._actions:
                raise ValueError(f"Two actions answer the intent {action.intent}")
            self._actions[action.intent] = action
        missing = [intent.value for intent in Intent if intent not in self._actions]
        if missing:
            raise ValueError(f"No action answers the intents: {', '.join(missing)}")

    def get(self, intent: Intent) -> DeterministicAction:
        """Returns the action that answers an intent.

        Args:
            intent: The intent to answer.

        Returns:
            DeterministicAction: its action.
        """
        return self._actions[intent]
