"""Assembles a `ConversationEngine` from its readers, its embedder and its settings.

Exists so the CLI, the web layer and the tests build the engine the same way and only choose
what differs: where customer data comes from, which models run (`IaModelsConfig`), and where
state lives.
"""

from krtr.back.ia.deterministic.actions.account_balance import AccountBalanceAction
from krtr.back.ia.deterministic.actions.complaint_status import ComplaintStatusAction
from krtr.back.ia.deterministic.config import DeterministicConfig
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
from krtr.back.ia.reasoning.llm.base import MeteredLlmClient
from krtr.back.ia.reasoning.llm.clarifier import LlmClarifier
from krtr.back.ia.reasoning.llm.factory import build_llm_client
from krtr.back.ia.reasoning.llm.guard import LlmGuardConfirmer
from krtr.back.ia.reasoning.llm.history import ConversationHistory
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter


def build_engine(
    products: CustomerProductsReader,
    complaints: CustomerComplaintsReader,
    store: ConversationStateStore,
    messages: MessageStore,
    config: EngineConfig | None = None,
) -> ConversationEngine:
    """Builds the engine: the selected models, deterministic actions, clarifier chain and writer.

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
        FileNotFoundError: if the selected LLM's converted build is not in the model cache.
    """
    settings = config or EngineConfig()
    actions = build_actions(products, complaints, settings.deterministic)
    embedder = build_embedder(settings.models.embedding, settings.models.model_cache)
    catalog = ExemplarCatalog.load(embedder, settings.catalog)
    detector = build_language_detector(settings.models.language)
    thresholds = load_thresholds(settings.models.embedding)
    writer = TemplateResponseWriter.load()
    llm, tasks = _build_llm(settings, writer)
    history = ConversationHistory(messages, settings.llm.history)
    template = TemplateClarifier(actions)
    clarifier = LlmClarifier(template, tasks, actions, history) if tasks else template
    confirmer = LlmGuardConfirmer(tasks, history) if tasks else None
    return ConversationEngine(
        embedder=embedder,
        matcher=IntentMatcher(catalog, thresholds),
        guardrails=GuardrailPolicy(settings.conversation, thresholds, confirmer=confirmer),
        resolver=TurnResolver(actions, clarifier, settings.conversation),
        actions=actions,
        writer=writer,
        store=store,
        messages=messages,
        language=ConversationLanguagePolicy(detector, settings.language),
        recent_messages_kept=settings.conversation.recent_messages_kept,
        llm=llm,
    )


def build_actions(
    products: CustomerProductsReader,
    complaints: CustomerComplaintsReader,
    config: DeterministicConfig,
) -> ActionRegistry:
    """Builds every deterministic action, one per intent.

    Exists so the engine and the LLM evaluation (which applies the actions' slot rules to the
    LLM's values) build the same actions.

    Args:
        products: Reads the customers' products.
        complaints: Reads the customers' complaints.
        config: The actions' settings (the complaint ID format).

    Returns:
        ActionRegistry: the registry.
    """
    return ActionRegistry(
        [
            AccountBalanceAction(products),
            ComplaintStatusAction(complaints, config.complaint_id_pattern),
        ]
    )


def _build_llm(
    settings: EngineConfig, writer: TemplateResponseWriter
) -> tuple[MeteredLlmClient | None, LlmTasks | None]:
    """Builds the selected LLM, metered, and the tasks that use it.

    Args:
        settings: The engine's settings (the LLM model, its cache and its limits).
        writer: Shows the options' labels in the prompts.

    Returns:
        tuple[MeteredLlmClient | None, LlmTasks | None]: both, or (None, None) for `none`.
    """
    client = build_llm_client(settings.models.llm, settings.models.model_cache, settings.llm)
    if client is None:
        return None, None
    metered = MeteredLlmClient(client)
    return metered, LlmTasks(metered, PromptCatalog.load(), writer)
