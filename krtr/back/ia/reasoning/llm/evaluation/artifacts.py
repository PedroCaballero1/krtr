"""Defines the LLM evaluation set and its report.

Exists so the free-form replies, the guard confirmations and the measured outcomes are typed
contracts shared by the loader, the runner and `krtr back ia evaluate-llm`.
"""

from enum import StrEnum

from pydantic import BaseModel

from krtr.back.ia.reasoning.llm.models import LlmModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

NO_ANSWER = "none"  # The expected answer when the reply gives no option / value.


class LlmTask(StrEnum):
    """Which closed task a case exercises (see `reasoning/llm/tasks.py`)."""

    CHOOSE_OPTION = "choose_option"
    EXTRACT_VALUE = "extract_value"
    CONFIRM_GUARD = "confirm_guard"


class LlmCase(BaseModel):
    """One question for the LLM and the answer it must give.

    `subject` is the slot, `request`, or the guard label; `expected` is an option, a value,
    `none`, or `true` / `false` for a confirmation.
    """

    language: InterfaceLanguage
    task: LlmTask
    subject: str
    options: list[str]
    reply: str
    expected: str


class TaskOutcome(BaseModel):
    """How one task did in one language."""

    task: LlmTask
    cases: int
    right: int
    wrong: int  # A wrong option or value; for confirmations, a false "yes" or a missed one.
    false_positives: int  # An answer where `none` / `false` was expected: the riskiest error.
    unavailable: int  # Timeouts or invalid output: the deterministic path answered instead.
    latency_ms_p50: float
    latency_ms_p95: float


class LlmLanguageReport(BaseModel):
    """One language's results, task by task."""

    language: InterfaceLanguage
    tasks: list[TaskOutcome]


class LlmEvaluationReport(BaseModel):
    """The full evaluation of one LLM. Rendered by `krtr back ia evaluate-llm`."""

    model: LlmModel
    languages: list[LlmLanguageReport]
