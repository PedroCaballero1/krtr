"""Defines the limits of every LLM call.

Exists so the latency budget of the doubtful turns (Q3-C), the size of the answers and of the
conversation sent as context are set once. Consumed by `reasoning/llm/factory.py` and
`engine/factory.py`.
"""

from pydantic import BaseModel, Field


class HistoryConfig(BaseModel):
    """How much of a case's earlier conversation each LLM prompt may carry.

    Exists because a longer prompt takes longer to read: past `LlmConfig.timeout_seconds` (or
    the model's context length) the call fails and the LLM stops helping, on exactly the long
    cases. The character limits also stop a customer from crowding the context out by
    repeatedly sending very long messages. Consumed by `reasoning/llm/history.py`.

    Measured on Qwen2.5-1.5B int4 (CPU), each character of history adds about 1.1 ms to a call
    (1.35 s without history). With 1200 characters of short messages, p95 was 2.8 s and the
    slowest call 3.1 s; the default of 1000 kept the slowest call at 2.52 s.
    """

    messages_kept: int = Field(default=10, ge=0)  # The newest earlier messages; 0 sends none.
    message_max_characters: int = Field(default=300, ge=1)  # Fits a numbered product question.
    max_characters: int = Field(default=1000, ge=0)  # All messages; past it, the oldest go.


class LlmConfig(BaseModel):
    """How long an LLM call may take, how much it may write, and how much context it reads.

    Exists so a slow call gives up and the deterministic answer is used instead (G16).
    """

    timeout_seconds: float = Field(default=2.5, gt=0)  # Q3-C: past it, the template answer.
    max_new_tokens: int = Field(default=48, ge=8)  # The answers are short JSON objects.
    history: HistoryConfig = Field(default_factory=HistoryConfig)
