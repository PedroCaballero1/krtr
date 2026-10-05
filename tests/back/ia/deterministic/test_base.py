"""Tests what every action inherits: missing slots, a closed slot's options, validation."""

import pytest
from pydantic import ValidationError

from krtr.back.ia.artifacts import CustomerContext
from krtr.back.ia.deterministic.artifacts import ProductType, SlotName
from krtr.back.ia.deterministic.intents import Intent
from tests.back.ia.fakes import CUSTOMER_ID, sample_registry


def test_missing_slots_are_the_required_ones_not_collected() -> None:
    """The slots model alone defines "enough information"."""
    action = sample_registry().get(Intent.ACCOUNT_BALANCE)

    assert action.missing_slots({}) == [SlotName.PRODUCT_TYPE]
    assert action.missing_slots({SlotName.PRODUCT_TYPE: ProductType.CREDIT_CARD}) == []


def test_a_closed_slot_lists_its_values_and_a_free_one_none() -> None:
    """An enum slot can be offered as options; a free text slot must be typed."""
    registry = sample_registry()

    balance_options = registry.get(Intent.ACCOUNT_BALANCE).slot_options(SlotName.PRODUCT_TYPE)
    complaint_options = registry.get(Intent.COMPLAINT_STATUS).slot_options(SlotName.COMPLAINT_ID)

    assert balance_options == [member.value for member in ProductType]
    assert complaint_options == []


def test_run_rejects_a_value_outside_the_slot_options() -> None:
    """A slot value no rule could have produced never reaches `execute`."""
    action = sample_registry().get(Intent.ACCOUNT_BALANCE)

    with pytest.raises(ValidationError):
        action.run(CustomerContext(customer_id=CUSTOMER_ID), {SlotName.PRODUCT_TYPE: "gold_bars"})
