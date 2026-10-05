"""Tests that the registry guarantees exactly one action per intent."""

import pytest

from krtr.back.ia.deterministic.actions.account_balance import AccountBalanceAction
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.readers import InMemoryProductsReader
from krtr.back.ia.deterministic.registry import ActionRegistry
from tests.back.ia.fakes import sample_registry


def test_each_intent_gets_its_action() -> None:
    """The registry returns the action that answers each intent."""
    registry = sample_registry()

    assert all(registry.get(intent).intent == intent for intent in Intent)


def test_an_intent_without_action_fails_when_built() -> None:
    """A gap is caught when the engine is built, not mid-conversation."""
    with pytest.raises(ValueError, match="complaint_status"):
        ActionRegistry([AccountBalanceAction(InMemoryProductsReader({}))])


def test_two_actions_for_one_intent_fail() -> None:
    """A duplicate would make the answer depend on registration order."""
    reader = InMemoryProductsReader({})
    with pytest.raises(ValueError, match="Two actions"):
        ActionRegistry([AccountBalanceAction(reader), AccountBalanceAction(reader)])
