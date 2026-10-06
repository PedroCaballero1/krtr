"""Decides a message's intent from its similarity to the catalog's example phrases.

Exists as the deterministic first step of every turn (docs/ia-proposal.md §3.1): a clear
match goes straight to an action with no model call; anything less clear goes to the
clarifier with its top candidates. Consumed by `engine/engine.py`.
"""

import logging
from operator import attrgetter

import numpy as np

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate, MatchKind, MatchResult
from krtr.back.ia.matching.catalog import CatalogLabel, ExemplarCatalog
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.matching.thresholds import LanguageThresholds
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)


class IntentMatcher:
    """Applies the threshold + margin rule to a message's scores.

    Exists so the rule is one tested unit, independent of which embedder produced the scores.
    Built by `engine/factory.py`.
    """

    def __init__(self, catalog: ExemplarCatalog, thresholds: LanguageThresholds) -> None:
        """Keeps the catalog and the rule's thresholds for each language.

        Args:
            catalog: The embedded example phrases.
            thresholds: When a score counts as a match, per language.
        """
        self._catalog = catalog
        self._thresholds = thresholds

    def match(self, vector: np.ndarray, language: InterfaceLanguage) -> MatchResult:
        """Scores a message and classifies it as matched, ambiguous or no match.

        Args:
            vector: The message's L2-normalised embedding.
            language: The turn's language, whose thresholds apply.

        Returns:
            MatchResult: the verdict, the top intents and any guard flags.
        """
        thresholds = self._thresholds[language]
        scores = self._catalog.best_scores(vector)
        candidates = rank_intents(scores)[: thresholds.top_k]
        guard_flags = [label for label in GuardLabel if scores.get(label, 0.0) >= thresholds.guard]
        kind = classify(candidates, thresholds, rival_score(scores))
        top_label = max(scores, key=scores.__getitem__) if scores else None
        logger.debug("Matched %s: %s, flags %s", kind, candidates, guard_flags)
        return MatchResult(
            kind=kind, candidates=candidates, guard_flags=guard_flags, top_label=top_label
        )


def classify(
    candidates: list[MatchCandidate], thresholds: MatchThresholds, rival: float = 0.0
) -> MatchKind:
    """Applies the threshold + margin rule to ranked intents.

    Exists as a function so `krtr back ia evaluate` sweeps thresholds with the exact rule the
    matcher applies.

    Args:
        candidates: The intents, best first.
        thresholds: The rule's thresholds.
        rival: The best guard label's score: the lead must also hold over it.

    Returns:
        MatchKind: `MATCHED` only with a high score and a clear lead over the second intent
        and over every guard label.
    """
    best = candidates[0].score
    second = max(candidates[1].score if len(candidates) > 1 else 0.0, rival)
    if best < thresholds.reject:
        return MatchKind.NO_MATCH
    if best >= thresholds.accept and best - second >= thresholds.margin:
        return MatchKind.MATCHED
    return MatchKind.AMBIGUOUS


def rival_score(scores: dict[CatalogLabel, float]) -> float:
    """Returns the best guard label's score, the intents' strongest rival.

    Args:
        scores: The best score of every catalog label.

    Returns:
        float: the highest guard score, or 0 if no guard label has phrases.
    """
    return max((scores.get(label, 0.0) for label in GuardLabel), default=0.0)


def rank_intents(scores: dict[CatalogLabel, float]) -> list[MatchCandidate]:
    """Keeps the intents' scores, best first.

    Args:
        scores: The best score of every catalog label.

    Returns:
        list[MatchCandidate]: one candidate per intent, sorted by descending score.
    """
    candidates = [MatchCandidate(intent=intent, score=scores.get(intent, 0.0)) for intent in Intent]
    return sorted(candidates, key=attrgetter("score"), reverse=True)
