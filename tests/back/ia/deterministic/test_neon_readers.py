"""Tests the Neon readers: customer-scoped queries and the mapping of stored labels."""

from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from krtr.back.ia.deterministic.artifacts import ComplaintStatus, ProductType
from krtr.back.ia.deterministic.neon_readers import (
    STORED_PRODUCT_TYPES,
    NeonComplaintsReader,
    NeonProductsReader,
)


class FakeNeonClient:
    """Stands in for NeonClient: returns canned rows and remembers each query's parameters."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        """Answers every query with `rows`."""
        self.rows = rows
        self.params: list[dict[str, Any]] = []

    def fetch_all(self, statement: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Returns every canned row."""
        self.params.append(params)
        return self.rows

    def fetch_one(self, statement: str, params: dict[str, Any]) -> tuple[Any, ...] | None:
        """Returns the first canned row, or None."""
        self.params.append(params)
        return self.rows[0] if self.rows else None


def test_every_product_type_maps_to_a_stored_label() -> None:
    """A type without a label would crash the balance action for that question."""
    assert set(STORED_PRODUCT_TYPES) == set(ProductType)


def test_products_are_read_for_the_customer_by_their_stored_label() -> None:
    """The query is scoped to the session's customer and uses the source data's Spanish label."""
    client = FakeNeonClient([("4001220077810000", "COP", Decimal("10.50"), None)])

    products = NeonProductsReader(client).list_products("C1", ProductType.SAVINGS_ACCOUNT)

    assert client.params == [{"customer_id": "C1", "product_type": "Cuenta Ahorro"}]
    assert products[0].product_type == ProductType.SAVINGS_ACCOUNT
    assert products[0].current_balance == Decimal("10.50")
    assert products[0].credit_limit is None


def test_a_credit_product_keeps_its_limit() -> None:
    """Cards and loans answer with their limit next to the balance."""
    client = FakeNeonClient([("5412", "COP", Decimal("800"), Decimal("5000"))])

    [card] = NeonProductsReader(client).list_products("C1", ProductType.CREDIT_CARD)

    assert card.credit_limit == Decimal("5000")


def test_a_complaint_is_read_only_for_its_customer() -> None:
    """Both the ID and the customer are in the query, so another customer's complaint is None."""
    row = ("CMP-J7LT0TPC5YC33ULTQJZD", datetime(2026, 9, 1, 14, 30), "Technical", "In Process")
    client = FakeNeonClient([row])

    complaint = NeonComplaintsReader(client).find("C1", "CMP-J7LT0TPC5YC33ULTQJZD")

    assert client.params == [{"customer_id": "C1", "complaint_id": "CMP-J7LT0TPC5YC33ULTQJZD"}]
    assert complaint is not None
    assert complaint.status == ComplaintStatus.IN_PROCESS
    assert complaint.created_on.isoformat() == "2026-09-01"


def test_a_missing_complaint_is_none() -> None:
    """No row: the action answers "not found", the same as for another customer's complaint."""
    assert NeonComplaintsReader(FakeNeonClient([])).find("C1", "CMP-X") is None


def test_an_unknown_stored_status_fails_fast() -> None:
    """A status outside the catalog would have no translation; it must not pass silently."""
    row = ("CMP-1", datetime(2026, 9, 1), "Technical", "Pending Review")

    with pytest.raises(ValueError):
        NeonComplaintsReader(FakeNeonClient([row])).find("C1", "CMP-1")
