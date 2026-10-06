"""Reads customers' products and complaints from Neon for the deterministic actions.

Exists so the chat served by krtr-web answers with each customer's real data (the `products`
and `complaints` tables), through the same protocols the in-memory readers implement. Every
query filters by the session's `customer_id`. Consumed by `krtr/back/web/chat/agent.py`.
"""

import logging
from typing import Any

from krtr.back.ia.deterministic.artifacts import (
    ComplaintRecord,
    ComplaintStatus,
    ProductBalance,
    ProductType,
)
from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

_SELECT_BALANCES = load_sql("products", "select_balances_by_customer.sql")
_SELECT_COMPLAINT = load_sql("complaints", "select_for_customer.sql")

# How `products.product_type` labels each ProductType (the source data is in Spanish).
STORED_PRODUCT_TYPES: dict[ProductType, str] = {
    ProductType.SAVINGS_ACCOUNT: "Cuenta Ahorro",
    ProductType.CHECKING_ACCOUNT: "Cuenta Corriente",
    ProductType.CREDIT_CARD: "Tarjeta Crédito",
    ProductType.DEBIT_CARD: "Tarjeta Débito",
    ProductType.PERSONAL_LOAN: "Préstamo Personal",
    ProductType.MORTGAGE: "Préstamo Hipotecario",
    ProductType.INVESTMENT: "Inversión",
}


class NeonProductsReader:
    """Reads a customer's products of one type from the `products` table.

    Exists as the production `CustomerProductsReader`. Consumed by the balance action.
    """

    def __init__(self, client: NeonClient) -> None:
        """Builds the reader on a pooled Neon client.

        Args:
            client: The pooled Neon client (`fetch_all`).
        """
        self._client = client

    def list_products(self, customer_id: str, product_type: ProductType) -> list[ProductBalance]:
        """Lists the customer's open products of one type, oldest first.

        Args:
            customer_id: The customer whose products to read, from the session.
            product_type: The type to filter by.

        Returns:
            list[ProductBalance]: the matching products, possibly empty.
        """
        rows = self._client.fetch_all(
            _SELECT_BALANCES,
            {"customer_id": customer_id, "product_type": STORED_PRODUCT_TYPES[product_type]},
        )
        logger.debug("Read %d %s products", len(rows), product_type.value)
        return [_product_from(row, product_type) for row in rows]


class NeonComplaintsReader:
    """Reads one of a customer's complaints from the `complaints` table.

    Exists as the production `CustomerComplaintsReader`. Consumed by the complaint-status action.
    """

    def __init__(self, client: NeonClient) -> None:
        """Builds the reader on a pooled Neon client.

        Args:
            client: The pooled Neon client (`fetch_one`).
        """
        self._client = client

    def find(self, customer_id: str, complaint_id: str) -> ComplaintRecord | None:
        """Finds one complaint of the customer.

        Args:
            customer_id: The customer who must own the complaint, from the session.
            complaint_id: The complaint to find.

        Returns:
            ComplaintRecord | None: the complaint, or None if it does not exist or belongs to
            another customer.
        """
        row = self._client.fetch_one(
            _SELECT_COMPLAINT, {"customer_id": customer_id, "complaint_id": complaint_id}
        )
        if row is None:
            return None
        found_id, created_at, category, status = row
        return ComplaintRecord(
            complaint_id=found_id,
            created_on=created_at.date(),
            category=category,
            status=ComplaintStatus(status),
        )


def _product_from(row: tuple[Any, ...], product_type: ProductType) -> ProductBalance:
    """Builds a product from a `select_balances_by_customer.sql` row.

    Args:
        row: The row, in the query's column order.
        product_type: The type the rows were filtered by.

    Returns:
        ProductBalance: the product.
    """
    product_number, currency, current_balance, credit_limit = row
    return ProductBalance(
        product_number=product_number,
        product_type=product_type,
        currency=currency,
        current_balance=current_balance,
        credit_limit=credit_limit,
    )
