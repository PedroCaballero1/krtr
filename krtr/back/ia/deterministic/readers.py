"""Defines how the deterministic actions read customer data, always scoped to one customer.

Exists so an action never builds a query itself: it asks a reader for *this* customer's
products or complaints, and every reader filters by `customer_id`, which comes from the
session (`CustomerContext`). The in-memory readers back the `krtr back ia` CLI and the tests;
Neon readers implement the same protocols later.
"""

from typing import Protocol

from krtr.back.ia.deterministic.artifacts import (
    ComplaintRecord,
    ProductBalance,
    ProductType,
)


class CustomerProductsReader(Protocol):
    """Reads a customer's products. Consumed by the balance action."""

    def list_products(self, customer_id: str, product_type: ProductType) -> list[ProductBalance]:
        """Lists the customer's products of one type.

        Args:
            customer_id: The customer whose products to read.
            product_type: The type to filter by.

        Returns:
            list[ProductBalance]: the matching products, possibly empty.
        """
        ...


class CustomerComplaintsReader(Protocol):
    """Reads a customer's complaints. Consumed by the complaint-status action."""

    def find(self, customer_id: str, complaint_id: str) -> ComplaintRecord | None:
        """Finds one complaint of the customer.

        Args:
            customer_id: The customer who must own the complaint.
            complaint_id: The complaint to find.

        Returns:
            ComplaintRecord | None: the complaint, or None if it does not exist or belongs to
            another customer — both cases look the same to the caller.
        """
        ...


class InMemoryProductsReader:
    """Serves products from memory, keyed by customer.

    Exists for the `krtr back ia` CLI and the tests, which need realistic data without Neon.
    """

    def __init__(self, products_by_customer: dict[str, list[ProductBalance]]) -> None:
        """Stores the products to serve.

        Args:
            products_by_customer: Each customer's products, keyed by `customer_id`.
        """
        self._products_by_customer = products_by_customer

    def list_products(self, customer_id: str, product_type: ProductType) -> list[ProductBalance]:
        """Lists the customer's products of one type.

        Args:
            customer_id: The customer whose products to read.
            product_type: The type to filter by.

        Returns:
            list[ProductBalance]: the matching products, possibly empty.
        """
        products = self._products_by_customer.get(customer_id, [])
        return [product for product in products if product.product_type == product_type]


class InMemoryComplaintsReader:
    """Serves complaints from memory, keyed by customer.

    Exists for the `krtr back ia` CLI and the tests, which need realistic data without Neon.
    """

    def __init__(self, complaints_by_customer: dict[str, list[ComplaintRecord]]) -> None:
        """Stores the complaints to serve.

        Args:
            complaints_by_customer: Each customer's complaints, keyed by `customer_id`.
        """
        self._complaints_by_customer = complaints_by_customer

    def find(self, customer_id: str, complaint_id: str) -> ComplaintRecord | None:
        """Finds one complaint, only among the customer's own.

        Args:
            customer_id: The customer who must own the complaint.
            complaint_id: The complaint to find.

        Returns:
            ComplaintRecord | None: the complaint, or None if this customer has no such one.
        """
        complaints = self._complaints_by_customer.get(customer_id, [])
        return next((item for item in complaints if item.complaint_id == complaint_id), None)
