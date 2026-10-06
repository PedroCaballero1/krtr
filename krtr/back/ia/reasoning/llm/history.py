"""Loads a case's earlier messages for the LLM, only when an LLM task is about to run.

Exists so the LLM reads a reply in the context of its conversation without the clear turns
paying for it: the messages are read from the `MessageStore` (encrypted at rest) on the
doubtful turns only, and never copied into the conversation's state. Consumed by
`reasoning/llm/clarifier.py` and `reasoning/llm/guard.py`; built by `engine/factory.py`.
"""

import logging

from krtr.back.ia.messages.artifacts import ConversationMessage
from krtr.back.ia.messages.store import MessageStore
from krtr.back.ia.reasoning.artifacts import ConversationState
from krtr.back.ia.reasoning.llm.artifacts import ConversationTranscript, TranscriptEntry
from krtr.back.ia.reasoning.llm.config import HistoryConfig

logger = logging.getLogger(__name__)

TRUNCATION_MARKER = " […]"  # Ends a message that was shortened to fit.


class ConversationHistory:
    """Reads the newest messages of a case as a transcript that fits the context limits.

    Exists so the size of the context sent to the LLM is capped in one place: each message is
    shortened past its own limit, and past the message count or the total character budget the
    oldest messages are dropped. This keeps the prompt inside the LLM's time budget, however
    long or repeated the customer's messages are.
    """

    def __init__(self, messages: MessageStore, config: HistoryConfig) -> None:
        """Keeps the message store and the limits.

        Args:
            messages: The store the engine writes every message and reply to.
            config: How many messages, and how many characters, the transcript may hold.
        """
        self._messages = messages
        self._config = config

    def load(self, state: ConversationState) -> ConversationTranscript:
        """Builds the transcript of the case's earlier messages, oldest first.

        The message being handled is not in it: the engine stores it at the end of the turn.

        Args:
            state: The conversation, whose customer and incident identify the case.

        Returns:
            ConversationTranscript: the newest messages that fit the limits, oldest first.
        """
        if self._config.messages_kept == 0 or self._config.max_characters == 0:
            return ConversationTranscript()
        messages = self._messages.list_case(state.customer_id, state.incident_id)
        entries = self._fit(messages[-self._config.messages_kept :])
        logger.debug(
            "Kept %d of %d earlier messages for incident %s",
            len(entries),
            len(messages),
            state.incident_id,
        )
        return ConversationTranscript(entries=entries)

    def _fit(self, messages: list[ConversationMessage]) -> list[TranscriptEntry]:
        """Keeps the newest messages within the character budget, shortening long ones.

        Walks from the newest message back. Each message is cut to its own limit and to what
        is left of the budget; once the budget is spent, the older messages are dropped, so
        the transcript stays one unbroken stretch of the conversation.

        Args:
            messages: The candidate messages, oldest first.

        Returns:
            list[TranscriptEntry]: the kept messages, oldest first.
        """
        remaining = self._config.max_characters
        kept: list[TranscriptEntry] = []
        for message in reversed(messages):
            if remaining == 0:
                break
            text = message.content.strip()
            limit = min(self._config.message_max_characters, remaining)
            remaining -= min(len(text), limit)
            kept.append(TranscriptEntry(sender=message.sender, content=_shorten(text, limit)))
        return list(reversed(kept))


def _shorten(text: str, limit: int) -> str:
    """Cuts a text to a number of characters, marking the cut.

    Args:
        text: The message's text.
        limit: The most characters of the text to keep.

    Returns:
        str: the text itself if it fits, or its first `limit` characters and the marker.
    """
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + TRUNCATION_MARKER
