"""A scripted LLM for the phase 3 tests: it answers from a queue, or is unavailable."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.llm.artifacts import ConversationTranscript, TranscriptEntry
from krtr.back.ia.reasoning.llm.base import LlmClient, LlmUnavailable, SchemaT
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID


class ScriptedLlm(LlmClient):
    """Returns the queued answers in order, validated against each call's schema.

    An answer of `UNAVAILABLE` raises `LlmUnavailable`, as a timeout would.
    """

    def __init__(self, *answers: dict[str, Any] | str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.schemas: list[type[BaseModel]] = []

    def complete(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        answer = self.answers.pop(0)
        if answer == UNAVAILABLE:
            raise LlmUnavailable("scripted timeout")
        return schema.model_validate(answer)


UNAVAILABLE = "unavailable"
NO_HISTORY = ConversationTranscript()


def tasks_with(llm: ScriptedLlm) -> LlmTasks:
    """Builds the real tasks on a scripted LLM, with the shipped prompts and labels."""
    return LlmTasks(llm, PromptCatalog.load(), TemplateResponseWriter.load())


def transcript(*messages: tuple[MessageSender, str]) -> ConversationTranscript:
    """Builds a transcript from (sender, text) pairs, oldest first."""
    return ConversationTranscript(
        entries=[TranscriptEntry(sender=sender, content=content) for sender, content in messages]
    )


class CountingMessageStore(InMemoryMessageStore):
    """Counts how often the case's messages are read, to prove when the history is loaded."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def list_case(self, customer_id: str, incident_id: str) -> list[ConversationMessage]:
        self.reads += 1
        return super().list_case(customer_id, incident_id)


def stored_message(
    sender: MessageSender, content: str, incident_id: str = "I"
) -> ConversationMessage:
    """Builds a Spanish message of CUSTOMER_ID's case, as the engine stores it."""
    return ConversationMessage(
        incident_id=incident_id,
        customer_id=CUSTOMER_ID,
        sender=sender,
        content=content,
        language=InterfaceLanguage.SPANISH,
        sent_at=datetime(2026, 10, 6, tzinfo=UTC),
    )
