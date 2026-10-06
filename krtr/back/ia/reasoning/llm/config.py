"""Defines the limits of every LLM call.

Exists so the latency budget of the doubtful turns (Q3-C) and the size of the answers are set
once. Consumed by `reasoning/llm/factory.py`.
"""

from pydantic import BaseModel, Field


class LlmConfig(BaseModel):
    """How long an LLM call may take and how much it may write.

    Exists so a slow call gives up and the deterministic answer is used instead (G16).
    """

    timeout_seconds: float = Field(default=2.5, gt=0)  # Q3-C: past it, the template answer.
    max_new_tokens: int = Field(default=48, ge=8)  # The answers are short JSON objects.
