"""Assembles a `ConversationEngine` from its readers, its embedder and its settings.

Exists so the CLI, the web layer and the tests build the engine the same way and only choose
what differs: where customer data comes from, which models run (`IaModelsConfig`), and where
state lives.
"""

from krtr.back.ia.deterministic.actions.account_balance import AccountBalanceAction
from krtr.back.ia.deterministic.actions.complaint_status import ComplaintStatusAction
from krtr.back.ia.deterministic.readers import (
    CustomerComplaintsReader,
    CustomerProductsReader,
)
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.engine.config import EngineConfig
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.engine.store import ConversationStateStore
from krtr.back.ia.guardrails.policy import GuardrailPolicy
from krtr.back.ia.language.factory import build_language_detector
from krtr.back.ia.language.policy import ConversationLanguagePolicy
from krtr.back.ia.matching.catalog import ExemplarCatalog
from krtr.back.ia.matching.factory import build_embedder
from krtr.back.ia.matching.matcher import IntentMatcher
from krtr.back.ia.matching.thresholds import load_thresholds
from krtr.back.ia.messages.store import MessageStore
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter


def build_engine(
    products: CustomerProductsReader,
    complaints: CustomerComplaintsReader,
    store: ConversationStateStore,
    messages: MessageStore,
    config: EngineConfig | None = None,
) -> ConversationEngine:
    """Builds the engine: the selected models, deterministic actions, template clarifier and writer.

    The embedder and the language detector come from `config.models`, so the thresholds
    loaded always belong to the embedding model that runs.

    Args:
        products: Reads the customers' products.
        complaints: Reads the customers' complaints.
        store: Keeps each conversation's state.
        messages: Keeps the text of each message and reply.
        config: The settings; the defaults when None.

    Returns:
        ConversationEngine: the ready engine.

    Raises:
        ValueError: if the catalog, the templates, the thresholds or the registry are incomplete.
    """
    settings = config or EngineConfig()
    actions = ActionRegistry(
        [
            AccountBalanceAction(products),
            ComplaintStatusAction(complaints, settings.deterministic.complaint_id_pattern),
        ]
    )
    embedder = build_embedder(settings.models.embedding, settings.models.model_cache)
    catalog = ExemplarCatalog.load(embedder, settings.catalog)
    detector = build_language_detector(settings.models.language)
    thresholds = load_thresholds(settings.models.embedding)
    return ConversationEngine(
        embedder=embedder,
        matcher=IntentMatcher(catalog, thresholds),
        guardrails=GuardrailPolicy(settings.conversation, thresholds),
        resolver=TurnResolver(actions, TemplateClarifier(actions), settings.conversation),
        actions=actions,
        writer=TemplateResponseWriter.load(),
        store=store,
        messages=messages,
        language=ConversationLanguagePolicy(detector, settings.language),
        recent_messages_kept=settings.conversation.recent_messages_kept,
    )
