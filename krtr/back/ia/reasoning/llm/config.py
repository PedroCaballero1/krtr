"""Defines the limits of every LLM call.

Exists so the LLM's time budget per turn, the size of the answers and of the conversation sent
as context are set once. Consumed by `reasoning/llm/factory.py` and
`engine/factory.py`.
"""

from pydantic import BaseModel, Field


class HistoryConfig(BaseModel):
    """How much of a case's earlier conversation each LLM prompt may carry.

    Exists because a longer prompt takes longer to read: past the turn's LLM budget (or the
    model's context length) the call fails and the LLM stops helping, on exactly the long
    cases. The character limits also stop a customer from crowding the context out by
    repeatedly sending very long messages. Consumed by `reasoning/llm/history.py`.

    Measured on Qwen2.5-1.5B int4 (CPU), each character of history adds about 1.1 ms to a call
    (1.35 s without history). With 1200 characters of short messages, p95 was 2.8 s and the
    slowest call 3.1 s. The default of 1000 keeps a call well inside the turn's LLM budget.
    """

    messages_kept: int = Field(default=10, ge=0)  # The newest earlier messages; 0 sends none.
    message_max_characters: int = Field(default=300, ge=1)  # Fits a numbered product question.
    max_characters: int = Field(default=1000, ge=0)  # All messages; past it, the oldest go.


class LlmConfig(BaseModel):
    """How much LLM time a turn may use, how much it may write, and how much context it reads.

    Exists so a slow turn gives up and the deterministic answer is used instead (G16).
    """

    # All the LLM calls of one turn share it; past it, the template answer is used. 3.5 s leaves
    # room for the rest of a turn inside the 4 s response-time SLA (G16, revised 2026-10-06).
    turn_budget_seconds: float = Field(default=3.5, gt=0)
    # A call is started only if the longest call still fits: reading the prompt is nearly all of
    # a call and can't be interrupted. The longest call measured with a full history (1000
    # characters) took 2.52 s, so on that CPU a turn makes one LLM call, and the turn stays
    # inside the SLA. On faster hardware, a second call fits on its own.
    min_call_seconds: float = Field(default=2.75, gt=0)
    max_new_tokens: int = Field(default=48, ge=8)  # The answers are short JSON objects.
    history: HistoryConfig = Field(default_factory=HistoryConfig)
