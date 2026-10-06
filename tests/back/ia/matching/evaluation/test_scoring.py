"""Tests that scoring records the intents' strongest rival and the cross-label pairs."""

import numpy as np

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.evaluation.artifacts import EvaluationCase
from krtr.back.ia.matching.evaluation.scoring import score_language
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.fakes import FixedEmbedder, catalog_of, unit

SPANISH = InterfaceLanguage.SPANISH
CATALOG = catalog_of(
    {
        Intent.ACCOUNT_BALANCE: [unit(1, 0, 0)],
        Intent.COMPLAINT_STATUS: [unit(0, 1, 0)],
        GuardLabel.UNSUPPORTED: [unit(0, 0, 1)],
    }
)
CASES = [
    EvaluationCase(language=SPANISH, expected=Intent.ACCOUNT_BALANCE, text="saldo"),
    EvaluationCase(language=SPANISH, expected=Intent.ACCOUNT_BALANCE, text="saldo de ahorros"),
    EvaluationCase(language=SPANISH, expected=GuardLabel.UNSUPPORTED, text="bloquear tarjeta"),
]
EMBEDDER = FixedEmbedder(
    {
        "saldo": unit(1, 0, 0.5),
        "saldo de ahorros": unit(1, 0, 0),
        "bloquear tarjeta": unit(0, 0, 1),
    },
    dimensions=3,
)


def test_the_rival_is_the_best_of_the_second_intent_and_the_guards() -> None:
    """A guard label scoring above the second intent is the lead to beat."""
    scores = score_language(EMBEDDER, CATALOG, CASES, [])

    assert scores.best[0] == np.float32(unit(1, 0, 0.5)[0])
    assert scores.second[0] == np.float32(unit(1, 0, 0.5)[2])
    assert scores.best_is_expected[0] and scores.expects_intent[0]
    assert scores.expects_guard[2] and scores.expected_guard_score[2] == 1.0


def test_only_pairs_with_different_labels_bound_the_repeat_threshold() -> None:
    """The two balance messages share a label, so only the two cross pairs are kept."""
    scores = score_language(EMBEDDER, CATALOG, CASES, [])

    assert scores.cross_label_similarity.size == 2
    assert len(scores.embed_ms) == len(CASES)
