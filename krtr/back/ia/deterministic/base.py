"""Defines the contract every deterministic action follows.

Exists so the resolver can treat every intent the same way: ask the action what inputs it
needs, let it pull them from the text, list the options of a closed input, and finally run
it. Consumed by `deterministic/registry.py` and `reasoning/resolver.py`; implemented under
`deterministic/actions/`.
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

from krtr.back.ia.artifacts import CustomerContext, ReplyContent
from krtr.back.ia.deterministic.intents import Intent

SlotsT = TypeVar("SlotsT", bound=BaseModel)


class DeterministicAction(ABC, Generic[SlotsT]):
    """One intent's fixed answer: validated inputs in, facts out, no model involved.

    Exists so "enough information" is defined by `slots_model` — every required field —
    instead of by any component's judgement (docs/ia-proposal.md §2.2). Subclasses declare
    `intent` and `slots_model` and implement `extract_slots` and `execute`.
    """

    intent: ClassVar[Intent]
    slots_model: ClassVar[type[BaseModel]]

    @abstractmethod
    def extract_slots(self, text: str) -> dict[str, str]:
        """Pulls whichever of this action's inputs the text states.

        Args:
            text: The raw customer text.

        Returns:
            dict[str, str]: the inputs found, by slot name; missing ones are left out.
        """

    @abstractmethod
    def execute(self, context: CustomerContext, slots: SlotsT) -> ReplyContent:
        """Runs the action for the session's customer.

        Args:
            context: The customer, from the session.
            slots: The validated inputs.

        Returns:
            ReplyContent: the facts to phrase.
        """

    def missing_slots(self, collected: dict[str, str]) -> list[str]:
        """Lists the required inputs not collected yet, in declaration order.

        Exists so the resolver knows whether to run the action or to ask for the next input.

        Args:
            collected: The inputs gathered so far in the conversation.

        Returns:
            list[str]: the names of the missing required slots.
        """
        fields = self.slots_model.model_fields
        return [
            name for name, field in fields.items() if field.is_required() and name not in collected
        ]

    def slot_options(self, slot: str) -> list[str]:
        """Lists the values a closed input accepts, so the clarifier can offer them.

        Args:
            slot: The slot's name.

        Returns:
            list[str]: the enum values of a closed slot, or an empty list for a free one.
        """
        annotation = self.slots_model.model_fields[slot].annotation
        if isinstance(annotation, type) and issubclass(annotation, StrEnum):
            return [member.value for member in annotation]
        return []

    def run(self, context: CustomerContext, collected: dict[str, str]) -> ReplyContent:
        """Validates the collected inputs and executes the action.

        Args:
            context: The customer, from the session.
            collected: Every required input, by slot name.

        Returns:
            ReplyContent: the facts to phrase.

        Raises:
            pydantic.ValidationError: if an input is missing or invalid.
        """
        return self.execute(context, self.slots_model.model_validate(collected))
