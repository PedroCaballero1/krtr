"""Tests the outcome counts and the threshold rules on hand-built scores."""

import numpy as np
import pytest

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchCandidate
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.evaluation.scoring import LanguageScores
from krtr.back.ia.matching.evaluation.sweep import (
    MIN_SAFETY_GAP,
    count_outcomes,
    propose_thresholds,
)
from krtr.back.ia.matching.matcher import classify

CURRENT = MatchThresholds(accept=0.8, reject=0.4, margin=0.1, guard=0.8, repeat=0.9)


def _scores(
    cases: list[tuple[float, float, str]], pairs: list[tuple[float, bool]]
) -> LanguageScores:
    """Builds scores from (best, rival, kind) cases; kind is right, wrong, none or guard:<score>."""
    scores = LanguageScores(len(cases), len(pairs))
    for row, (best, rival, kind) in enumerate(cases):
        scores.best[row], scores.second[row] = best, rival
        scores.expects_intent[row] = kind in ("right", "wrong")
        scores.best_is_expected[row] = kind == "right"
        if kind.startswith("guard:"):
            scores.expects_guard[row] = True
            scores.expected_guard_score[row] = scores.max_guard_score[row] = float(kind[6:])
    for row, (similarity, same) in enumerate(pairs):
        scores.pair_similarity[row], scores.pair_same[row] = similarity, same
    return scores


SCORES = _scores(
    [
        (0.90, 0.40, "right"),  # Lead 0.50.
        (0.75, 0.60, "right"),  # Lead 0.15.
        (0.70, 0.62, "none"),  # A message the catalog doesn't cover, leading by 0.08.
        (0.50, 0.30, "none"),
        (0.30, 0.20, "guard:0.85"),
    ],
    [(0.95, True), (0.85, False)],
)


def test_counts_follow_the_matcher_rule() -> None:
    """With margin 0.1, the uncovered message (lead 0.08) is not answered."""
    counts = count_outcomes(SCORES, MatchThresholds(accept=0.6, reject=0.4, margin=0.1))

    assert (counts.matched_right, counts.matched_wrong) == (2, 0)
    assert (counts.ambiguous, counts.no_match) == (2, 1)


def test_answering_an_uncovered_message_counts_as_wrong() -> None:
    """Without enough margin, the uncovered message gets an answer: the worst outcome."""
    counts = count_outcomes(SCORES, MatchThresholds(accept=0.6, reject=0.4, margin=0.05))

    assert counts.matched_wrong == 1


def test_the_margin_clears_the_riskiest_lead_by_the_safety_gap() -> None:
    """The uncovered message leads by 0.08, so the margin is 0.08 + gap."""
    proposed = propose_thresholds(SCORES, CURRENT)

    assert proposed.margin == pytest.approx(0.08 + MIN_SAFETY_GAP)
    assert count_outcomes(SCORES, proposed).matched_wrong == 0


def test_accept_keeps_every_right_match_that_clears_the_margin() -> None:
    """The weakest right match (0.75) is still answered, with the gap below it."""
    proposed = propose_thresholds(SCORES, CURRENT)

    assert proposed.accept == pytest.approx(0.75 - MIN_SAFETY_GAP)
    assert count_outcomes(SCORES, proposed).matched_right == 2


def test_reject_never_sends_a_catalog_message_to_rephrase() -> None:
    """Catalog messages that miss the match get the options, not "say it another way"."""
    proposed = propose_thresholds(SCORES, CURRENT)

    assert proposed.reject <= 0.75
    assert proposed.reject < proposed.accept


def test_guard_and_repeat_cutoffs_let_no_false_positive_through() -> None:
    """The repeat cutoff sits above the `different` pair (0.85): only the `same` one is caught."""
    proposed = propose_thresholds(SCORES, CURRENT)
    counts = count_outcomes(SCORES, proposed)

    assert (counts.repeat_caught, counts.repeat_false) == (1, 0)
    assert (counts.guard_right, counts.guard_false) == (1, 0)


def test_without_negatives_the_current_cutoffs_are_kept() -> None:
    """With no pairs to measure against, the repeat threshold is not guessed."""
    scores = _scores([(0.9, 0.1, "right")], [])

    assert propose_thresholds(scores, CURRENT).repeat == CURRENT.repeat


@pytest.mark.parametrize("seed", range(5))
def test_the_vectorised_rule_agrees_with_the_matcher(seed: int) -> None:
    """The sweep must count exactly what `matcher.classify` would decide."""
    generator = np.random.default_rng(seed)
    best, rival = np.sort(generator.random((2, 50)), axis=0)[::-1]
    scores = _scores([(b, r, "right") for b, r in zip(best, rival)], [])
    thresholds = MatchThresholds(accept=0.5, reject=0.2, margin=0.1)
    expected = sum(
        classify(
            [MatchCandidate(intent=Intent.ACCOUNT_BALANCE, score=b)],
            thresholds,
            rival=r,
        ).value
        == "matched"
        for b, r in zip(best, rival)
    )

    assert count_outcomes(scores, thresholds).matched_right == expected
