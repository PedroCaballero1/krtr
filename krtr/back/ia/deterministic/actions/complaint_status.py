"""Answers "how is my complaint going?" for one complaint of the customer.

Exists because following up an open complaint is the most common reason to contact the bank
again (three in four complaints are still active). Registered by `engine/factory.py`.
"""

import re

from pydantic import BaseModel, Field

from krtr.back.ia.artifacts import CustomerContext, MessageKey, ReplyContent
from krtr.back.ia.deterministic.artifacts import SlotName
from krtr.back.ia.deterministic.base import DeterministicAction
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.readers import CustomerComplaintsReader
from krtr.back.ia.deterministic.slot_extraction import extract_pattern


class ComplaintStatusSlots(BaseModel):
    """The complaint-status action's inputs: which complaint."""

    complaint_id: str = Field(min_length=1)


class ComplaintStatusAction(DeterministicAction[ComplaintStatusSlots]):
    """Shows the status of one of the customer's complaints.

    Exists as the `COMPLAINT_STATUS` intent's action. A complaint that does not exist and one
    that belongs to someone else get the same answer, so the reply never confirms that
    another customer's complaint exists (G13).
    """

    intent = Intent.COMPLAINT_STATUS
    slots_model = ComplaintStatusSlots

    def __init__(self, complaints: CustomerComplaintsReader, complaint_id_pattern: str) -> None:
        """Keeps the reader and compiles the identifier format.

        Args:
            complaints: Reads the customer's complaints.
            complaint_id_pattern: The regular expression a complaint ID matches.
        """
        self._complaints = complaints
        self._complaint_id_pattern = re.compile(complaint_id_pattern)

    def extract_slots(self, text: str) -> dict[str, str]:
        """Finds a complaint ID in the text.

        Args:
            text: The raw customer text.

        Returns:
            dict[str, str]: `{SlotName.COMPLAINT_ID: ...}`, or empty if the text has none.
        """
        complaint_id = extract_pattern(text, self._complaint_id_pattern)
        return {SlotName.COMPLAINT_ID: complaint_id} if complaint_id else {}

    def execute(self, context: CustomerContext, slots: ComplaintStatusSlots) -> ReplyContent:
        """Looks the complaint up among the customer's own and shows its status.

        Args:
            context: The customer, from the session.
            slots: The validated complaint ID.

        Returns:
            ReplyContent: the status, or `COMPLAINT_NOT_FOUND`.
        """
        record = self._complaints.find(context.customer_id, slots.complaint_id)
        if record is None:
            return ReplyContent(
                message_key=MessageKey.COMPLAINT_NOT_FOUND,
                values={SlotName.COMPLAINT_ID: slots.complaint_id},
            )
        values = {
            SlotName.COMPLAINT_ID: record.complaint_id,
            "status": record.status.value,
            "category": record.category,
            "created_on": record.created_on.isoformat(),
        }
        return ReplyContent(message_key=MessageKey.COMPLAINT_STATUS, values=values)
