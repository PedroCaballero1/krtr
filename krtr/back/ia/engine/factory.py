"""Assembles a `ConversationEngine` from its readers, its embedder and its settings.

Exists so the CLI, the web layer and the tests build the engine the same way and only choose
what differs: where customer data comes from, which embedder runs, and where state lives.
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
from krtr.back.ia.language.base import LanguageDetector
from krtr.back.ia.language.policy import ConversationLanguagePolicy
from krtr.back.ia.language.py3langid_detector import Py3LangidLanguageDetector
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.catalog import ExemplarCatalog
from krtr.back.ia.matching.matcher import IntentMatcher
from krtr.back.ia.reasoning.clarifier import TemplateClarifier
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter


def build_engine(
    embedder: Embedder,
    products: CustomerProductsReader,
    complaints: CustomerComplaintsReader,
    store: ConversationStateStore,
    config: EngineConfig | None = None,
    language_detector: LanguageDetector | None = None,
) -> ConversationEngine:
    """Builds the phase 1 engine: deterministic actions, template clarifier and writer.

    Args:
        embedder: Embeds the catalog once and each message per turn.
        products: Reads the customers' products.
        complaints: Reads the customers' complaints.
        store: Keeps each conversation's state.
        config: The settings; the defaults when None.
        language_detector: Guesses each message's language; py3langid when None.

    Returns:
        ConversationEngine: the ready engine.

    Raises:
        ValueError: if the catalog, the templates or the registry are incomplete.
    """
    settings = config or EngineConfig()
    actions = ActionRegistry(
        [
            AccountBalanceAction(products),
            ComplaintStatusAction(complaints, settings.deterministic.complaint_id_pattern),
        ]
    )
    catalog = ExemplarCatalog.load(embedder, settings.catalog)
    return ConversationEngine(
        embedder=embedder,
        matcher=IntentMatcher(catalog, settings.thresholds),
        guardrails=GuardrailPolicy(settings.conversation),
        resolver=TurnResolver(actions, TemplateClarifier(actions), settings.conversation),
        actions=actions,
        writer=TemplateResponseWriter.load(),
        store=store,
        language=ConversationLanguagePolicy(
            language_detector or Py3LangidLanguageDetector(), settings.language
        ),
        recent_messages_kept=settings.conversation.recent_messages_kept,
    )
