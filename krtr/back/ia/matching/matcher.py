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

logger = logging.getLogger(__name__)


class IntentMatcher:
    """Applies the threshold + margin rule to a message's scores.

    Exists so the rule is one tested unit, independent of which embedder produced the scores.
    Built by `engine/factory.py`.
    """

    def __init__(self, catalog: ExemplarCatalog, thresholds: MatchThresholds) -> None:
        """Keeps the catalog and the rule's thresholds.

        Args:
            catalog: The embedded example phrases.
            thresholds: When a score counts as a match.
        """
        self._catalog = catalog
        self._thresholds = thresholds

    def match(self, vector: np.ndarray) -> MatchResult:
        """Scores a message and classifies it as matched, ambiguous or no match.

        Args:
            vector: The message's L2-normalised embedding.

        Returns:
            MatchResult: the verdict, the top intents and any guard flags.
        """
        scores = self._catalog.best_scores(vector)
        candidates = _rank_intents(scores)[: self._thresholds.top_k]
        guard_flags = [
            label for label in GuardLabel if scores.get(label, 0.0) >= self._thresholds.guard
        ]
        kind = self._classify(candidates)
        logger.debug("Matched %s: %s, flags %s", kind, candidates, guard_flags)
        return MatchResult(kind=kind, candidates=candidates, guard_flags=guard_flags)

    def _classify(self, candidates: list[MatchCandidate]) -> MatchKind:
        """Applies the rule to the ranked intents.

        Args:
            candidates: The intents, best first.

        Returns:
            MatchKind: `MATCHED` only with a high score and a clear lead over the second.
        """
        best = candidates[0].score
        second = candidates[1].score if len(candidates) > 1 else 0.0
        if best < self._thresholds.reject:
            return MatchKind.NO_MATCH
        if best >= self._thresholds.accept and best - second >= self._thresholds.margin:
            return MatchKind.MATCHED
        return MatchKind.AMBIGUOUS


def _rank_intents(scores: dict[CatalogLabel, float]) -> list[MatchCandidate]:
    """Keeps the intents' scores, best first.

    Args:
        scores: The best score of every catalog label.

    Returns:
        list[MatchCandidate]: one candidate per intent, sorted by descending score.
    """
    candidates = [MatchCandidate(intent=intent, score=scores.get(intent, 0.0)) for intent in Intent]
    return sorted(candidates, key=attrgetter("score"), reverse=True)
