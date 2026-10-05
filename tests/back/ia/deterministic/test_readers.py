"""Tests that the in-memory readers only ever return the asked customer's data."""

from krtr.back.ia.demo import DEMO_COMPLAINT_ID, DEMO_COMPLAINTS, DEMO_PRODUCTS
from krtr.back.ia.deterministic.artifacts import ProductType
from krtr.back.ia.deterministic.readers import (
    InMemoryComplaintsReader,
    InMemoryProductsReader,
)
from tests.back.ia.fakes import CUSTOMER_ID, OTHER_CUSTOMER_ID


def test_products_are_filtered_by_customer_and_type() -> None:
    """Only the customer's products of the asked type come back."""
    reader = InMemoryProductsReader({CUSTOMER_ID: DEMO_PRODUCTS})

    products = reader.list_products(CUSTOMER_ID, ProductType.CREDIT_CARD)

    assert [product.product_type for product in products] == [ProductType.CREDIT_CARD]
    assert reader.list_products(OTHER_CUSTOMER_ID, ProductType.CREDIT_CARD) == []


def test_another_customers_complaint_is_not_found() -> None:
    """A complaint ID that exists, but for someone else, looks like a missing one."""
    reader = InMemoryComplaintsReader({CUSTOMER_ID: DEMO_COMPLAINTS})

    assert reader.find(CUSTOMER_ID, DEMO_COMPLAINT_ID) == DEMO_COMPLAINTS[0]
    assert reader.find(OTHER_CUSTOMER_ID, DEMO_COMPLAINT_ID) is None
