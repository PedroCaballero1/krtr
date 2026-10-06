"""Defines the conversation rules of the `krtr/back/ia/` vertical.

Exists so the limits that bound a conversation — how many clarifications before escalating
(G19, G20) and how many repeats before closing (G13) — are declared once. Consumed by
`reasoning/resolver.py` and `guardrails/policy.py`.
"""

from pydantic import BaseModel, Field


class IaConfig(BaseModel):
    """The conversation limits.

    Exists so the resolver, the guardrails and their tests share the same numbers instead of
    repeating them. Consumed by `reasoning/resolver.py` and `guardrails/policy.py`.
    """

    max_clarification_turns: int = Field(default=3, ge=1)  # Over it, the case is escalated.
    repetition_limit: int = Field(default=3, ge=2)  # The same message this many times closes it.
    recent_messages_kept: int = Field(default=10, ge=2)  # Window for the repetition rule.
