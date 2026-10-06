"""Builds an engine over sample customer data, for trying conversations without Neon or a model.

Exists so `krtr back ia` can run the full pipeline on any machine: in-memory products and
complaints for one demo customer, the selected models, and in-memory state and messages.
Consumed by `krtr/cli/back/ia/handler.py`.
"""

from datetime import date
from decimal import Decimal

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.deterministic.artifacts import (
    ComplaintRecord,
    ComplaintStatus,
    ProductBalance,
    ProductType,
)
from krtr.back.ia.deterministic.readers import (
    InMemoryComplaintsReader,
    InMemoryProductsReader,
)
from krtr.back.ia.engine.config import EngineConfig
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.engine.factory import build_engine
from krtr.back.ia.engine.store import InMemoryConversationStateStore
from krtr.back.ia.messages.store import InMemoryMessageStore

DEMO_CUSTOMER_ID = "CUST-DEMO"
DEMO_INCIDENT_ID = "INC-DEMO"
DEMO_COMPLAINT_ID = "PQR-104233"

DEMO_PRODUCTS = [
    ProductBalance(
        product_number="4001-2200-7781",
        product_type=ProductType.SAVINGS_ACCOUNT,
        currency="COP",
        current_balance=Decimal("2350400.50"),
    ),
    ProductBalance(
        product_number="5412-7710-0043-9921",
        product_type=ProductType.CREDIT_CARD,
        currency="COP",
        current_balance=Decimal("812300.00"),
        credit_limit=Decimal("5000000.00"),
    ),
]

DEMO_COMPLAINTS = [
    ComplaintRecord(
        complaint_id=DEMO_COMPLAINT_ID,
        created_on=date(2026, 9, 14),
        category="Fees",
        status=ComplaintStatus.IN_PROCESS,
    ),
]


def build_demo_engine(models: IaModelsConfig) -> ConversationEngine:
    """Builds the engine over the demo customer's sample data, with the selected models.

    Args:
        models: Which embedding model and language detector run.

    Returns:
        ConversationEngine: an engine whose only customer is `DEMO_CUSTOMER_ID`.
    """
    return build_engine(
        products=InMemoryProductsReader({DEMO_CUSTOMER_ID: DEMO_PRODUCTS}),
        complaints=InMemoryComplaintsReader({DEMO_CUSTOMER_ID: DEMO_COMPLAINTS}),
        store=InMemoryConversationStateStore(),
        messages=InMemoryMessageStore(),
        config=EngineConfig(models=models),
    )
