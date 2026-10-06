"""Defines when a message is clear enough to set the conversation's language.

Exists so the two gates of the policy — enough words, enough confidence — are tuned in one
place. Spanish and Portuguese share many words ("saldo", "banco"), so short messages are
never trusted. Consumed by `language/policy.py`.
"""

from pydantic import BaseModel, Field


class LanguageConfig(BaseModel):
    """The gates a message must pass to set or switch the conversation's language."""

    min_words: int = Field(default=3, ge=1)  # "1", "saldo" or an ID never count.
    min_confidence: float = Field(default=0.8, gt=0, le=1)
