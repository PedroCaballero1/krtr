"""Defines what a language detector returns.

Exists so the policy compares a typed guess against its confidence threshold instead of a
detector's raw output.
"""

from pydantic import BaseModel, Field

from krtr.back.security.oidc.artifacts import InterfaceLanguage


class LanguageGuess(BaseModel):
    """The likeliest language of a text, and how sure the detector is (0 to 1)."""

    language: InterfaceLanguage
    confidence: float = Field(ge=0, le=1)
