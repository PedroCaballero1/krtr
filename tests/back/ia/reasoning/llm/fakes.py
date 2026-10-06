"""A scripted LLM for the phase 3 tests: it answers from a queue, or is unavailable."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.ia.messages.store import InMemoryMessageStore
from krtr.back.ia.reasoning.llm.artifacts import ConversationTranscript, TranscriptEntry
from krtr.back.ia.reasoning.llm.base import LlmClient, LlmUnavailable, MeteredLlmClient, SchemaT
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import CUSTOMER_ID


class PerfCounterClock:
    """A `time.perf_counter` stand-in, in seconds, that only moves when told to."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ScriptedLlm(LlmClient):
    """Returns the queued answers in order, validated against each call's schema.

    An answer of `UNAVAILABLE` raises `LlmUnavailable`, as a timeout would. Each call records the
    time it was given and, with a `clock`, advances it by `seconds_per_call`.
    """

    def __init__(
        self,
        *answers: dict[str, Any] | str,
        clock: PerfCounterClock | None = None,
        seconds_per_call: float = 0.0,
    ) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.schemas: list[type[BaseModel]] = []
        self.timeouts: list[float] = []
        self.clock = clock
        self.seconds_per_call = seconds_per_call

    def complete(self, prompt: str, schema: type[SchemaT], timeout_seconds: float) -> SchemaT:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        self.timeouts.append(timeout_seconds)
        if self.clock is not None:
            self.clock.now += self.seconds_per_call
        answer = self.answers.pop(0)
        if answer == UNAVAILABLE:
            raise LlmUnavailable("scripted timeout")
        return schema.model_validate(answer)


UNAVAILABLE = "unavailable"
NO_HISTORY = ConversationTranscript()


def metered(llm: ScriptedLlm, config: LlmConfig | None = None) -> MeteredLlmClient:
    """Wraps a scripted LLM with a turn budget, by default the shipped one."""
    settings = config or LlmConfig()
    clock = llm.clock or PerfCounterClock()
    return MeteredLlmClient(
        llm, settings.turn_budget_seconds, settings.min_call_seconds, clock=clock
    )


def tasks_with(llm: ScriptedLlm) -> LlmTasks:
    """Builds the real tasks on a scripted LLM, with the shipped prompts, labels and budget."""
    return LlmTasks(metered(llm), PromptCatalog.load(), TemplateResponseWriter.load())


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
