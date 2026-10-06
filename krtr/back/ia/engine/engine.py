"""Runs one customer message through the whole pipeline and returns the agent's reply.

Exists as the only entry point the web chat endpoint and `krtr back ia` call
(docs/ia-proposal.md §2.1): the reply language, hard rules, intent matching, resolution, an
action or a question, then the template writer, saving the conversation's state at the end
storing the message and the reply (G17), and timing every step (G16).
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime

from krtr.back.ia.artifacts import (
    AgentReply,
    CustomerContext,
    MessageKey,
    ReplyContent,
    TurnDetails,
    TurnOutcome,
    TurnStep,
    TurnTimings,
    UserTurn,
)
from krtr.back.ia.deterministic.registry import ActionRegistry
from krtr.back.ia.engine.content import ending_content, question_content
from krtr.back.ia.engine.store import ConversationStateStore
from krtr.back.ia.guardrails.policy import GuardrailPolicy
from krtr.back.ia.language.policy import ConversationLanguagePolicy
from krtr.back.ia.matching.artifacts import MatchResult
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.matcher import IntentMatcher
from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.ia.messages.store import MessageStore
from krtr.back.ia.reasoning.artifacts import (
    ConversationState,
    NeedsClarification,
    Resolution,
    Resolved,
)
from krtr.back.ia.reasoning.resolver import TurnResolver
from krtr.back.ia.text import normalize_text
from krtr.back.ia.timing import StepTimer
from krtr.back.ia.writing.base import ResponseWriter
from krtr.back.security.clock import Clock, utc_now
from krtr.back.security.oidc.artifacts import InterfaceLanguage

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
        messages: MessageStore,
        recent_messages_kept: int,
        clock: Callable[[], float] = time.perf_counter,
        now: Clock = utc_now,
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
            messages: Stores the text of each message and reply.
            recent_messages_kept: How many past messages the repetition rule looks at.
            clock: Returns the current time in seconds, for timing the turn.
            now: Returns the current UTC time, for the messages' timestamps.
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
        self._clock = clock
        self._now = now
        self._messages = messages

    def handle(self, turn: UserTurn) -> AgentReply:
        """Answers one message of a case, timing each step of the turn.

        Args:
            turn: The message, its case, the session's customer and the caller's language.

        Returns:
            AgentReply: the reply text, its language, how the turn ended and how long it took.
        """
        timer = StepTimer(self._clock)
        received_at = self._now()
        logger.info("Handling a message for incident %s", turn.incident_id)
        state = self._store.load(turn.customer_id, turn.incident_id)
        with timer.measure(TurnStep.LANGUAGE):
            language = self._language.resolve(state, turn.text, turn.language)
        content, outcome, details = self._run_turn(state, turn, timer)
        with timer.measure(TurnStep.WRITING):
            reply = self._writer.write(content, language)
        with timer.measure(TurnStep.PERSISTENCE):
            self._store.save(state)
            self._record_messages(turn, received_at, reply, language, outcome)
        timings = timer.finish()
        _log_turn(turn.incident_id, outcome, timings)
        return AgentReply(
            incident_id=turn.incident_id,
            reply=reply,
            language=language,
            outcome=outcome,
            timings=timings,
            details=details,
        )

    def _record_messages(
        self,
        turn: UserTurn,
        received_at: datetime,
        reply: str,
        language: InterfaceLanguage,
        outcome: TurnOutcome,
    ) -> None:
        """Stores the customer's message and the agent's reply in the case's messages (G17).

        Args:
            turn: The customer's message and its case.
            received_at: When the message arrived.
            reply: The agent's reply text.
            language: The language of the turn.
            outcome: How the turn ended, stored on the reply.

        Returns:
            None.
        """
        case = {"incident_id": turn.incident_id, "customer_id": turn.customer_id}
        self._messages.append(
            ConversationMessage(
                **case,
                sender=MessageSender.CUSTOMER,
                content=turn.text,
                language=language,
                sent_at=received_at,
            )
        )
        self._messages.append(
            ConversationMessage(
                **case,
                sender=MessageSender.AGENT,
                content=reply,
                language=language,
                outcome=outcome,
                sent_at=self._now(),
            )
        )

    def _run_turn(
        self, state: ConversationState, turn: UserTurn, timer: StepTimer
    ) -> tuple[ReplyContent, TurnOutcome, TurnDetails]:
        """Resolves and applies the message, unless the conversation has already ended.

        Args:
            state: The conversation, updated in place.
            turn: The message and the session's customer.
            timer: Times the steps.

        Returns:
            tuple[ReplyContent, TurnOutcome, TurnDetails]: the facts to phrase, how the turn
            ended, and what was understood.
        """
        if state.ended is not None:
            ended = ReplyContent(message_key=MessageKey.CONVERSATION_ENDED)
            return ended, state.ended, TurnDetails()
        resolution, match = self._resolve(state, turn.text, timer)
        with timer.measure(TurnStep.ACTION):
            content = self._apply(state, resolution, CustomerContext(customer_id=turn.customer_id))
        self._remember(state, turn.text)
        return content, resolution.kind, _details(resolution, match)

    def _resolve(
        self, state: ConversationState, text: str, timer: StepTimer
    ) -> tuple[Resolution, MatchResult | None]:
        """Applies the hard rules, then embeds, matches and resolves the message.

        Args:
            state: The conversation so far.
            text: The customer's message.
            timer: Times the steps.

        Returns:
            tuple[Resolution, MatchResult | None]: what the turn does, and the matcher's verdict
            (None when a hard rule closed the conversation before matching).
        """
        with timer.measure(TurnStep.GUARDRAILS):
            closure = self._guardrails.check(state, text)
        if closure is not None:
            return closure, None
        with timer.measure(TurnStep.EMBEDDING):
            vector = self._embedder.embed([text])[0]
        with timer.measure(TurnStep.MATCHING):
            match = self._matcher.match(vector)
        if match.guard_flags:
            logger.warning("Guard flags %s on incident %s", match.guard_flags, state.incident_id)
        with timer.measure(TurnStep.RESOLUTION):
            return self._resolver.resolve(state, text, match), match

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


def _log_turn(incident_id: str, outcome: TurnOutcome, timings: TurnTimings) -> None:
    """Logs how a turn ended and how long it took, with the per-step breakdown at debug level.

    Args:
        incident_id: The case.
        outcome: How the turn ended.
        timings: The turn's durations.

    Returns:
        None.
    """
    logger.info("Incident %s turn ended as %s in %.2f ms", incident_id, outcome, timings.total_ms)
    steps = ", ".join(f"{step.value} {ms:.2f}" for step, ms in timings.steps_ms.items())
    logger.debug("Incident %s step durations (ms): %s", incident_id, steps)


def _details(resolution: Resolution, match: MatchResult | None) -> TurnDetails:
    """Collects what was understood in a turn, for its `events` metadata.

    Args:
        resolution: What the turn does.
        match: The matcher's verdict, or None if matching never ran.

    Returns:
        TurnDetails: the intent resolved or asked about, the match kind and any guard flags.
    """
    intent = None
    if isinstance(resolution, Resolved):
        intent = resolution.intent
    elif isinstance(resolution, NeedsClarification):
        intent = resolution.question.intent
    if match is None:
        return TurnDetails(intent=intent)
    return TurnDetails(intent=intent, match_kind=match.kind, guard_flags=match.guard_flags)
