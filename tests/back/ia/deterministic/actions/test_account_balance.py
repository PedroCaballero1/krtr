"""Tests the balance answer: the right products, masked numbers, credit limits, and none held."""

from decimal import Decimal

from krtr.back.ia.artifacts import CustomerContext, MessageKey
from krtr.back.ia.demo import DEMO_PRODUCTS
from krtr.back.ia.deterministic.actions.account_balance import (
    AccountBalanceAction,
    AccountBalanceSlots,
)
from krtr.back.ia.deterministic.artifacts import ProductBalance, ProductType, SlotName
from krtr.back.ia.deterministic.readers import InMemoryProductsReader
from tests.back.ia.fakes import CUSTOMER_ID

CONTEXT = CustomerContext(customer_id=CUSTOMER_ID)


def _action(products: list[ProductBalance]) -> AccountBalanceAction:
    return AccountBalanceAction(InMemoryProductsReader({CUSTOMER_ID: products}))


def test_credit_card_balance_shows_its_limit_and_masks_the_number() -> None:
    """A credit product answers with its limit; only the last 4 digits are shown."""
    content = _action(DEMO_PRODUCTS).execute(
        CONTEXT, AccountBalanceSlots(product_type=ProductType.CREDIT_CARD)
    )

    assert content.message_key == MessageKey.CREDIT_BALANCE
    assert content.items == [
        {
            "product_number": "****9921",
            "balance": "812,300.00",
            "currency": "COP",
            "credit_limit": "5,000,000.00",
        }
    ]


def test_each_product_of_the_type_is_listed() -> None:
    """Two savings accounts give two lines, with no limit message."""
    accounts = [
        ProductBalance(
            product_number=f"0000{last}",
            product_type=ProductType.SAVINGS_ACCOUNT,
            currency="USD",
            current_balance=Decimal(amount),
        )
        for last, amount in (("1111", "10"), ("2222", "1234.5"))
    ]

    content = _action(accounts).execute(
        CONTEXT, AccountBalanceSlots(product_type=ProductType.SAVINGS_ACCOUNT)
    )

    assert content.message_key == MessageKey.ACCOUNT_BALANCE
    assert [item["balance"] for item in content.items] == ["10.00", "1,234.50"]


def test_no_product_of_the_type_says_so() -> None:
    """Asking for a mortgage the customer doesn't have is answered, not escalated."""
    content = _action(DEMO_PRODUCTS).execute(
        CONTEXT, AccountBalanceSlots(product_type=ProductType.MORTGAGE)
    )

    assert content.message_key == MessageKey.NO_PRODUCTS
    assert content.values == {SlotName.PRODUCT_TYPE: ProductType.MORTGAGE.value}


def test_extract_slots_reads_the_product_type() -> None:
    """The product type named in the message fills the slot; none named leaves it out."""
    action = _action([])

    assert action.extract_slots("saldo de mi cuenta de ahorros") == {
        SlotName.PRODUCT_TYPE: ProductType.SAVINGS_ACCOUNT.value
    }
    assert action.extract_slots("cuál es mi saldo") == {}
