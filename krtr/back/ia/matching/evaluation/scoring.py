"""Scores the evaluation set once, so thresholds can be tried without re-embedding.

Exists because the threshold search tries thousands of combinations: the embedding (the slow
part) runs once per message here, and the search only compares numbers. Consumed by
`matching/evaluation/runner.py` and `matching/evaluation/sweep.py`.
"""

import time

import numpy as np

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.catalog import CatalogLabel, ExemplarCatalog
from krtr.back.ia.matching.evaluation.artifacts import EvaluationCase, PairKind, RepetitionPair
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.matching.matcher import rank_intents, rival_score
from krtr.back.ia.text import matching_text

MILLISECONDS_PER_SECOND = 1000


class LanguageScores:
    """One language's scores, as arrays aligned by case (or by pair).

    Exists as plain internal data for the search: not a contract, so not a pydantic model.
    """

    def __init__(self, case_count: int, pair_count: int) -> None:
        """Allocates the arrays.

        Args:
            case_count: How many labelled messages.
            pair_count: How many repetition pairs.
        """
        self.best = np.zeros(case_count)  # Best intent's score.
        self.second = np.zeros(case_count)  # Best rival: the second intent or a guard label.
        self.best_is_expected = np.zeros(case_count, dtype=bool)
        self.expects_intent = np.zeros(case_count, dtype=bool)
        self.expects_guard = np.zeros(case_count, dtype=bool)
        self.expected_guard_score = np.zeros(case_count)  # The expected guard label's score.
        self.max_guard_score = np.zeros(case_count)  # The highest guard label's score.
        self.pair_similarity = np.zeros(pair_count)
        self.pair_same = np.zeros(pair_count, dtype=bool)
        self.cross_label_similarity = np.zeros(0)  # Every pair of cases with different labels.
        self.embed_ms: list[float] = []


def score_language(
    embedder: Embedder,
    catalog: ExemplarCatalog,
    cases: list[EvaluationCase],
    pairs: list[RepetitionPair],
) -> LanguageScores:
    """Embeds and scores one language's cases and pairs.

    Args:
        embedder: The model under evaluation.
        catalog: The catalog embedded with that model.
        cases: The language's labelled messages.
        pairs: The language's repetition pairs.

    Returns:
        LanguageScores: the scores, ready for the threshold search.
    """
    scores = LanguageScores(len(cases), len(pairs))
    vectors = []
    for row, case in enumerate(cases):
        started_at = time.perf_counter()
        vector = embedder.embed([matching_text(case.text)])[0]
        scores.embed_ms.append((time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND)
        _record_case(scores, row, case, catalog.best_scores(vector))
        vectors.append(vector)
    scores.cross_label_similarity = _cross_label_similarity(cases, vectors)
    for row, pair in enumerate(pairs):
        first, second = embedder.embed([matching_text(pair.first), matching_text(pair.second)])
        scores.pair_similarity[row] = float(first @ second)
        scores.pair_same[row] = pair.kind == PairKind.SAME
    return scores


def _cross_label_similarity(cases: list[EvaluationCase], vectors: list[np.ndarray]) -> np.ndarray:
    """Collects the similarity of every pair of messages that ask different things.

    Exists so the repeat threshold is bounded by hundreds of "must not repeat" pairs, not only
    the few hand-written ones: two messages with different labels are never a repeat.

    Args:
        cases: The language's labelled messages.
        vectors: Their embeddings, in the same order.

    Returns:
        np.ndarray: one similarity per pair of cases with different expected labels.
    """
    if not vectors:
        return np.zeros(0)
    similarities = np.stack(vectors) @ np.stack(vectors).T
    labels = [case.expected for case in cases]
    rows, columns = np.triu_indices(len(cases), k=1)
    different = np.array([labels[row] != labels[column] for row, column in zip(rows, columns)])
    return similarities[rows, columns][different] if different.size else np.zeros(0)


def _record_case(
    scores: LanguageScores, row: int, case: EvaluationCase, label_scores: dict[CatalogLabel, float]
) -> None:
    """Stores one case's intent and guard scores.

    Args:
        scores: The arrays, updated in place.
        row: The case's row.
        case: The labelled message.
        label_scores: The catalog's best score per label.

    Returns:
        None.
    """
    ranked = rank_intents(label_scores)
    scores.best[row] = ranked[0].score
    scores.second[row] = max(ranked[1].score if len(ranked) > 1 else 0.0, rival_score(label_scores))
    scores.best_is_expected[row] = ranked[0].intent == case.expected
    scores.expects_intent[row] = isinstance(case.expected, Intent)
    scores.expects_guard[row] = isinstance(case.expected, GuardLabel)
    guard_scores = [label_scores.get(label, 0.0) for label in GuardLabel]
    scores.max_guard_score[row] = max(guard_scores)
    if isinstance(case.expected, GuardLabel):
        scores.expected_guard_score[row] = label_scores.get(case.expected, 0.0)
