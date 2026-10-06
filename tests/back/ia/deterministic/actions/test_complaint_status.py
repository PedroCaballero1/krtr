"""Tests the complaint-status answer, and that another customer's complaint stays invisible."""

from krtr.back.ia.artifacts import CustomerContext, MessageKey
from krtr.back.ia.demo import DEMO_COMPLAINT_ID, DEMO_COMPLAINTS
from krtr.back.ia.deterministic.actions.complaint_status import (
    ComplaintStatusAction,
    ComplaintStatusSlots,
)
from krtr.back.ia.deterministic.artifacts import SlotName
from krtr.back.ia.deterministic.config import DEFAULT_COMPLAINT_ID_PATTERN
from krtr.back.ia.deterministic.readers import InMemoryComplaintsReader
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID

ACTION = ComplaintStatusAction(
    InMemoryComplaintsReader({CUSTOMER_ID: DEMO_COMPLAINTS}), DEFAULT_COMPLAINT_ID_PATTERN
)


def test_own_complaint_shows_its_status() -> None:
    """The owner sees the status, category and creation date."""
    content = ACTION.execute(
        CustomerContext(customer_id=CUSTOMER_ID),
        ComplaintStatusSlots(complaint_id=DEMO_COMPLAINT_ID),
    )

    assert content.message_key == MessageKey.COMPLAINT_STATUS
    assert content.values == {
        SlotName.COMPLAINT_ID: DEMO_COMPLAINT_ID,
        "status": "In Process",
        "category": "Fees",
        "created_on": "2026-09-14",
    }


def test_another_customers_complaint_gets_the_same_answer_as_a_missing_one() -> None:
    """The reply never confirms that someone else's complaint exists (G13)."""
    slots = ComplaintStatusSlots(complaint_id=DEMO_COMPLAINT_ID)

    other = ACTION.execute(CustomerContext(customer_id=OTHER_CUSTOMER_ID), slots)
    missing = ACTION.execute(
        CustomerContext(customer_id=OTHER_CUSTOMER_ID),
        ComplaintStatusSlots(complaint_id="PQR-000001"),
    )

    assert other.message_key == missing.message_key == MessageKey.COMPLAINT_NOT_FOUND
    assert other.values == {SlotName.COMPLAINT_ID: DEMO_COMPLAINT_ID}


def test_extract_slots_reads_the_complaint_id() -> None:
    """An ID in the message fills the slot; none leaves it out."""
    assert ACTION.extract_slots("mi caso es pqr-104233") == {SlotName.COMPLAINT_ID: "PQR-104233"}
    assert ACTION.extract_slots("cómo va mi queja") == {}
