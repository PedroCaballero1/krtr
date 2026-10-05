"""Runs one customer message through the whole pipeline and returns the agent's reply.

Exists as the only entry point the web chat endpoint and `krtr back ia` call
(docs/ia-proposal.md §2.1): the reply language, hard rules, intent matching, resolution, an
action or a question, then the template writer, saving the conversation's state at the end.
"""

import logging

from krtr.back.ia.artifacts import (
    AgentReply,
    CustomerContext,
    MessageKey,
    ReplyContent,
    UserTurn,
)
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.engine.content import ending_content, question_content
from krtr.back.ia.engine.store import ConversationStateStore
from krtr.back.ia.guardrails.policy import GuardrailPolicy
from krtr.back.ia.language.policy import ConversationLanguagePolicy
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.matcher import IntentMatcher
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    Resolution,
    Resolved,
)
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.ia.text import normalize_text
from krtr.back.ia.writing.base import ResponseWriter

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Orchestrates a turn; it decides nothing itself.

    Exists so each step stays in its own component and the order of the steps lives in one
    place. Built by `engine/factory.py`.
    """

    def __init__(
        self,
        embedder: Embedder,
        matcher: IntentMatcher,
        guardrails: GuardrailPolicy,
        resolver: TurnResolver,
        actions: ActionRegistry,
        writer: ResponseWriter,
        store: ConversationStateStore,
        language: ConversationLanguagePolicy,
        recent_messages_kept: int,
    ) -> None:
        """Keeps the pipeline's components.

        Args:
            embedder: Embeds the message once per turn.
            matcher: Classifies the message against the catalog.
            guardrails: The deterministic hard rules.
            resolver: Decides what the turn does.
            actions: Runs the resolved intent.
            writer: Phrases the reply.
            store: Loads and saves the conversation's state.
            language: Decides the language each reply is written in.
            recent_messages_kept: How many past messages the repetition rule looks at.
        """
        self._embedder = embedder
        self._matcher = matcher
        self._guardrails = guardrails
        self._resolver = resolver
        self._actions = actions
        self._writer = writer
        self._store = store
        self._language = language
        self._recent_messages_kept = recent_messages_kept

    def handle(self, turn: UserTurn) -> AgentReply:
        """Answers one message of a case.

        Args:
            turn: The message, its case, the session's customer and the caller's language.

        Returns:
            AgentReply: the reply text, its language and how the turn ended.
        """
        logger.info("Handling a message for incident %s", turn.incident_id)
        state = self._store.load(turn.customer_id, turn.incident_id)
        language = self._language.resolve(state, turn.text, turn.language)
        if state.ended is not None:
            content, outcome = ReplyContent(message_key=MessageKey.CONVERSATION_ENDED), state.ended
        else:
            resolution = self._resolve(state, turn.text)
            content = self._apply(state, resolution, CustomerContext(customer_id=turn.customer_id))
            outcome = resolution.kind
            self._remember(state, turn.text)
        self._store.save(state)
        logger.info("Incident %s turn ended as %s", turn.incident_id, outcome)
        return AgentReply(
            incident_id=turn.incident_id,
            reply=self._writer.write(content, language),
            language=language,
            outcome=outcome,
        )

    def _resolve(self, state: ConversationState, text: str) -> Resolution:
        """Applies the hard rules, then matches and resolves the message.

        Args:
            state: The conversation so far.
            text: The customer's message.

        Returns:
            Resolution: what the turn does.
        """
        closure = self._guardrails.check(state, text)
        if closure is not None:
            return closure
        match = self._matcher.match(self._embedder.embed([text])[0])
        if match.guard_flags:
            logger.warning("Guard flags %s on incident %s", match.guard_flags, state.incident_id)
        return self._resolver.resolve(state, text, match)

    def _apply(
        self, state: ConversationState, resolution: Resolution, context: CustomerContext
    ) -> ReplyContent:
        """Runs the action or records the question or the ending, updating the state.

        Args:
            state: The conversation, updated in place.
            resolution: What the turn does.
            context: The session's customer.

        Returns:
            ReplyContent: the facts to phrase.
        """
        if isinstance(resolution, Resolved):
            state.pending, state.clarification_attempts = None, 0
            logger.info("Running %s for incident %s", resolution.intent, state.incident_id)
            return self._actions.get(resolution.intent).run(context, resolution.slots)
        if isinstance(resolution, NeedsClarification):
            state.pending = resolution.question
            state.clarification_attempts += 1
            return question_content(resolution)
        state.pending, state.ended = None, resolution.kind
        return ending_content(resolution)

    def _remember(self, state: ConversationState, text: str) -> None:
        """Adds the message to the window the repetition rule looks at.

        Args:
            state: The conversation, updated in place.
            text: The customer's message.

        Returns:
            None.
        """
        state.recent_messages = [*state.recent_messages, normalize_text(text)][
            -self._recent_messages_kept :
        ]
