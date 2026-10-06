"""Fakes shared by the ia tests: fixed vectors, a hand-built catalog, sample data and an engine."""

import numpy as np

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.demo import DEMO_COMPLAINTS, DEMO_PRODUCTS
from krtr.back.ia.deterministic.actions.account_balance import AccountBalanceAction
from krtr.back.ia.deterministic.actions.complaint_status import ComplaintStatusAction
from krtr.back.ia.deterministic.config import DEFAULT_COMPLAINT_ID_PATTERN
from krtr.back.ia.deterministic.readers import (
    InMemoryComplaintsReader,
    InMemoryProductsReader,
)
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.engine.config import EngineConfig
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.engine.factory import build_engine
from krtr.back.ia.engine.store import InMemoryConversationStateStore
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.catalog import CatalogLabel, ExemplarCatalog
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.llm.models import LlmModel

CUSTOMER_ID = "CUST-1"
OTHER_CUSTOMER_ID = "CUST-2"


def unit(*components: float) -> np.ndarray:
    """Builds an L2-normalised vector, so its dot products are cosine similarities."""
    vector = np.array(components, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def vector_with_similarity(similarity: float) -> np.ndarray:
    """Builds a 2-d unit vector whose dot product with (1, 0) is `similarity`."""
    return np.array([similarity, np.sqrt(1 - similarity**2)], dtype=np.float32)


def catalog_of(rows: dict[CatalogLabel, list[np.ndarray]]) -> ExemplarCatalog:
    """Builds a catalog directly from vectors, skipping files and embedders."""
    labels = [label for label, vectors in rows.items() for _ in vectors]
    matrix = np.stack([vector for vectors in rows.values() for vector in vectors])
    return ExemplarCatalog(labels, matrix)


class FixedEmbedder(Embedder):
    """Returns a preset vector per text, and a zero vector for any other text."""

    def __init__(self, vectors: dict[str, np.ndarray], dimensions: int) -> None:
        self._vectors = vectors
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        zero = np.zeros(self._dimensions, dtype=np.float32)
        return np.stack([self._vectors.get(text, zero) for text in texts])


def sample_registry() -> ActionRegistry:
    """Builds the real actions over the demo data, owned by CUSTOMER_ID."""
    return ActionRegistry(
        [
            AccountBalanceAction(InMemoryProductsReader({CUSTOMER_ID: DEMO_PRODUCTS})),
            ComplaintStatusAction(
                InMemoryComplaintsReader({CUSTOMER_ID: DEMO_COMPLAINTS}),
                DEFAULT_COMPLAINT_ID_PATTERN,
            ),
        ]
    )


HASHING_MODELS = IaModelsConfig(embedding=EmbeddingModel.HASHING, llm=LlmModel.NONE)  # Offline.


def sample_engine(messages: InMemoryMessageStore | None = None) -> ConversationEngine:
    """Builds the full engine over the demo data, owned by CUSTOMER_ID, with the hashing model."""
    return build_engine(
        products=InMemoryProductsReader({CUSTOMER_ID: DEMO_PRODUCTS}),
        complaints=InMemoryComplaintsReader({CUSTOMER_ID: DEMO_COMPLAINTS}),
        store=InMemoryConversationStateStore(),
        messages=messages or InMemoryMessageStore(),
        config=EngineConfig(models=HASHING_MODELS),
    )
