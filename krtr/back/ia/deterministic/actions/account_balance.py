"""Answers "what is my balance?" for one product type of the customer.

Exists because a balance request opens every call in the history, so it is the request the
deterministic fast path must cover first. Registered by `engine/factory.py`.
"""

from decimal import Decimal

from pydantic import BaseModel

from krtr.back.ia.artifacts import CustomerContext, MessageKey, ReplyContent
from krtr.back.ia.deterministic.artifacts import ProductBalance, ProductType, SlotName
from krtr.back.ia.deterministic.base import DeterministicAction
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.readers import CustomerProductsReader
from krtr.back.ia.deterministic.slot_extraction import extract_keyword_option

# Normalised (lower-case, no accents) ways of naming each product, in ES and PT.
PRODUCT_KEYWORDS: dict[ProductType, tuple[str, ...]] = {
    ProductType.SAVINGS_ACCOUNT: ("ahorro", "ahorros", "poupanca"),
    ProductType.CHECKING_ACCOUNT: ("cuenta corriente", "conta corrente"),
    ProductType.CREDIT_CARD: ("tarjeta de credito", "cartao de credito"),
    ProductType.DEBIT_CARD: ("tarjeta de debito", "cartao de debito"),
    ProductType.PERSONAL_LOAN: ("prestamo personal", "emprestimo pessoal"),
    ProductType.MORTGAGE: ("hipoteca", "hipotecario", "financiamento imobiliario"),
    ProductType.INVESTMENT: ("inversion", "inversiones", "investimento", "investimentos"),
}

VISIBLE_PRODUCT_DIGITS = 4  # Only the last digits of a product number are ever shown.


class AccountBalanceSlots(BaseModel):
    """The balance action's inputs: which kind of product."""

    product_type: ProductType


class AccountBalanceAction(DeterministicAction[AccountBalanceSlots]):
    """Lists the balance of each of the customer's products of the requested type.

    Exists as the `ACCOUNT_BALANCE` intent's action. Reads through a
    `CustomerProductsReader`, always for the session's customer.
    """

    intent = Intent.ACCOUNT_BALANCE
    slots_model = AccountBalanceSlots

    def __init__(self, products: CustomerProductsReader) -> None:
        """Keeps the reader the balances come from.

        Args:
            products: Reads the customer's products.
        """
        self._products = products

    def extract_slots(self, text: str) -> dict[str, str]:
        """Finds the product type the text names, if exactly one.

        Args:
            text: The raw customer text.

        Returns:
            dict[str, str]: `{SlotName.PRODUCT_TYPE: ...}`, or empty when none or several are named.
        """
        product_type = extract_keyword_option(text, PRODUCT_KEYWORDS)
        return {SlotName.PRODUCT_TYPE: product_type.value} if product_type else {}

    def execute(self, context: CustomerContext, slots: AccountBalanceSlots) -> ReplyContent:
        """Reads the customer's products of the type and lists their balances.

        Args:
            context: The customer, from the session.
            slots: The validated product type.

        Returns:
            ReplyContent: one item per product, with the credit limit for credit products,
            or `NO_PRODUCTS` when the customer holds none of that type.
        """
        products = self._products.list_products(context.customer_id, slots.product_type)
        values = {SlotName.PRODUCT_TYPE: slots.product_type.value}
        if not products:
            return ReplyContent(message_key=MessageKey.NO_PRODUCTS, values=values)
        has_limit = any(product.credit_limit is not None for product in products)
        message_key = MessageKey.CREDIT_BALANCE if has_limit else MessageKey.ACCOUNT_BALANCE
        items = [_balance_item(product) for product in products]
        return ReplyContent(message_key=message_key, values=values, items=items)


def _balance_item(product: ProductBalance) -> dict[str, str]:
    """Builds one product's line of facts, with its number masked.

    Args:
        product: The product to show.

    Returns:
        dict[str, str]: `product_number`, `balance`, `currency` and `credit_limit`.
    """
    return {
        "product_number": _mask(product.product_number),
        "balance": _format_amount(product.current_balance),
        "currency": product.currency,
        "credit_limit": _format_amount(product.credit_limit) if product.credit_limit else "-",
    }


def _mask(product_number: str) -> str:
    """Hides all but the last digits of a product number.

    Args:
        product_number: The full account, card or policy number.

    Returns:
        str: e.g. "****1234".
    """
    return f"****{product_number[-VISIBLE_PRODUCT_DIGITS:]}"


def _format_amount(amount: Decimal) -> str:
    """Formats an amount with two decimals and thousands separators.

    Args:
        amount: The amount to show.

    Returns:
        str: e.g. "12,345.60".
    """
    return f"{amount:,.2f}"
