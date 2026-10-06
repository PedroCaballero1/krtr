"""Tests that state is kept per customer and incident, and never shared by reference."""

from krtr.back.ia.engine.store import InMemoryConversationStateStore
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID


def test_another_customer_with_the_same_incident_id_gets_a_fresh_state() -> None:
    """Knowing someone's incident ID never loads their conversation."""
    store = InMemoryConversationStateStore()
    state = store.load(CUSTOMER_ID, "INC-1")
    state.clarification_attempts = 2
    store.save(state)

    assert store.load(CUSTOMER_ID, "INC-1").clarification_attempts == 2
    assert store.load(OTHER_CUSTOMER_ID, "INC-1").clarification_attempts == 0


def test_changing_a_loaded_state_does_not_change_the_saved_one() -> None:
    """Only `save` persists: a turn that fails midway leaves the old state intact."""
    store = InMemoryConversationStateStore()
    store.save(store.load(CUSTOMER_ID, "INC-1"))

    store.load(CUSTOMER_ID, "INC-1").recent_requests.append("hola")

    assert store.load(CUSTOMER_ID, "INC-1").recent_requests == []
