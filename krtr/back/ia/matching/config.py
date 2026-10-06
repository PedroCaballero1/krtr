"""Defines the thresholds of the similarity matcher and the catalog's minimum coverage.

Exists so the decision rule (docs/ia-proposal.md §3.1) is tuned in one place. The defaults
suit the hashing embedder of phase 1; phase 2 sets them from the evaluation set for the real
model, per language.
"""

from pydantic import BaseModel, Field, model_validator


class MatchThresholds(BaseModel):
    """When a similarity score counts as a match, as ambiguous, or as no match.

    Exists so the matcher and its tests share one rule. Consumed by `matching/matcher.py`.
    """

    accept: float = Field(default=0.55, gt=0, le=1)  # Best intent at least this: may match.
    reject: float = Field(default=0.25, ge=0, le=1)  # Best intent below this: no match.
    margin: float = Field(default=0.05, ge=0, le=1)  # Lead over the second intent to match.
    guard: float = Field(default=0.6, gt=0, le=1)  # A guard label at least this: flagged.
    repeat: float = Field(default=0.95, gt=0, le=1)  # An earlier message this similar: a repeat.
    top_k: int = Field(default=3, ge=2)  # Candidates kept for the clarifier.

    @model_validator(mode="after")
    def _reject_below_accept(self) -> "MatchThresholds":
        """Checks that the no-match threshold lies below the match threshold.

        Returns:
            MatchThresholds: the validated thresholds.

        Raises:
            ValueError: if `reject` is not below `accept`.
        """
        if self.reject >= self.accept:
            raise ValueError("reject must be lower than accept")
        return self


class CatalogConfig(BaseModel):
    """How many example phrases each intent needs in each language.

    Exists so a catalog with an uncovered intent or language fails when it loads. The phase 1
    seed has few phrases; phase 2 raises the minimum.
    """

    min_exemplars_per_language: int = Field(default=2, ge=1)
