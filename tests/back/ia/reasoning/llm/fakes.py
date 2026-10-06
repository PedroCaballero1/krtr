"""A scripted LLM for the phase 3 tests: it answers from a queue, or is unavailable."""

from typing import Any

from pydantic import BaseModel

from krtr.back.ia.reasoning.llm.base import LlmClient, LlmUnavailable, SchemaT
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter


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


def tasks_with(llm: ScriptedLlm) -> LlmTasks:
    """Builds the real tasks on a scripted LLM, with the shipped prompts and labels."""
    return LlmTasks(llm, PromptCatalog.load(), TemplateResponseWriter.load())
