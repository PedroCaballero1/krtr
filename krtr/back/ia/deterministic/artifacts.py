"""Defines the customer data the deterministic actions read.

Exists to keep the records the readers return — a product's balance, a complaint's status —
apart from the actions that phrase them, so a Neon reader can later return the same shapes
the in-memory reader does. Consumed by `deterministic/readers.py` and `deterministic/actions/`.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class SlotName(StrEnum):
    """The inputs the deterministic actions ask for, named as their slots models' fields.

    Exists so slot names are typed where they cross components (extraction, questions,
    templates) instead of repeated as literals.
    """

    PRODUCT_TYPE = "product_type"
    COMPLAINT_ID = "complaint_id"


class ProductType(StrEnum):
    """The product types a customer can ask a balance for.

    Exists so the balance action's slot has a closed set of options the clarifier can list.
    Mirrors `products.product_type`; a Neon reader maps the stored labels to these members.
    """

    SAVINGS_ACCOUNT = "savings_account"
    CHECKING_ACCOUNT = "checking_account"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    INVESTMENT = "investment"


class ComplaintStatus(StrEnum):
    """The statuses a complaint can be in, as `complaints.status` stores them.

    Exists so the status shown to the customer is one of a known set, translated by the
    template catalogs.
    """

    OPEN = "Open"
    IN_PROCESS = "In Process"
    ESCALATED = "Escalated"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    REJECTED = "Rejected"


class ProductBalance(BaseModel):
    """One product of the customer, with what its balance answer shows.

    Exists as the return shape of `CustomerProductsReader.list_products`.
    """

    product_number: str
    product_type: ProductType
    currency: str
    current_balance: Decimal
    credit_limit: Decimal | None = None


class ComplaintRecord(BaseModel):
    """One complaint of the customer, with what its status answer shows.

    Exists as the return shape of `CustomerComplaintsReader.find`.
    """

    complaint_id: str
    created_on: date
    category: str
    status: ComplaintStatus
