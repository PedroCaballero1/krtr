"""Defines what the similarity matcher returns.

Exists so the resolver and the clarifier read one typed result — match, ambiguous or no
match, with its candidates and guard flags — instead of raw scores.
"""

from enum import StrEnum

from pydantic import BaseModel

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.labels import GuardLabel

CatalogLabel = Intent | GuardLabel


class MatchKind(StrEnum):
    """How sure the matcher is about the message's intent (docs/ia-proposal.md §3.1)."""

    MATCHED = "matched"  # Best intent above `accept` and clearly ahead of the second.
    AMBIGUOUS = "ambiguous"  # Plausible, but not clear enough: the customer chooses.
    NO_MATCH = "no_match"  # Best intent below `reject`.


class MatchCandidate(BaseModel):
    """One intent and its best similarity to the message."""

    intent: Intent
    score: float


class MatchResult(BaseModel):
    """The matcher's verdict on one message.

    Exists as the return contract of `IntentMatcher.match`. `candidates` are sorted by score,
    best first; on `MATCHED` the first one is the match.
    """

    kind: MatchKind
    candidates: list[MatchCandidate]
    guard_flags: list[GuardLabel] = []
    top_label: CatalogLabel | None = None  # The best label of all, intents and guards alike.

    @property
    def best_intent(self) -> Intent | None:
        """Returns the matched intent.

        Returns:
            Intent | None: the first candidate on `MATCHED`, otherwise None.
        """
        return self.candidates[0].intent if self.kind == MatchKind.MATCHED else None
