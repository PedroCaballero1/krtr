"""Counts what a set of thresholds does, and searches for the safest useful set.

Exists so thresholds are measured, not guessed (docs/ia-proposal.md §3.1). The search never
accepts a wrong match: a wrong match answers a question the customer didn't ask, so it costs
more than an extra clarification. Among the safe options, it keeps the one that answers the
most messages directly. Consumed by `matching/evaluation/runner.py`.
"""

import numpy as np

from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.evaluation.artifacts import OutcomeCounts
from krtr.back.ia.matching.evaluation.scoring import LanguageScores

GRID = np.round(np.arange(0.05, 1.0, 0.01), 2)  # Candidate values for every threshold.
ACCEPTS = GRID[GRID >= 0.3]  # Below 0.3 a "match" barely resembles any catalog phrase.
MARGINS = np.round(np.arange(0.0, 0.31, 0.01), 2)
MIN_SAFETY_GAP = 0.03  # Distance (in similarity) every threshold keeps from the measured cases.


def count_outcomes(scores: LanguageScores, thresholds: MatchThresholds) -> OutcomeCounts:
    """Applies a set of thresholds to every scored case and pair.

    The match rule is `matcher.classify`, vectorised; a test pins that both agree.

    Args:
        scores: One language's scores.
        thresholds: The thresholds to try.

    Returns:
        OutcomeCounts: how many cases land on each outcome.
    """
    matched = _matched(scores, thresholds.accept, thresholds.margin)
    no_match = ~matched & (scores.best < thresholds.reject)
    flagged = scores.max_guard_score >= thresholds.guard
    repeats = scores.pair_similarity >= thresholds.repeat
    cross_repeats = scores.cross_label_similarity >= thresholds.repeat
    return OutcomeCounts(
        matched_right=int((matched & scores.expects_intent & scores.best_is_expected).sum()),
        matched_wrong=int((matched & ~(scores.expects_intent & scores.best_is_expected)).sum()),
        ambiguous=int((~matched & ~no_match).sum()),
        no_match=int(no_match.sum()),
        guard_right=int(
            (scores.expects_guard & (scores.expected_guard_score >= thresholds.guard)).sum()
        ),
        guard_false=int((flagged & ~scores.expects_guard).sum()),
        repeat_caught=int((repeats & scores.pair_same).sum()),
        repeat_false=int((repeats & ~scores.pair_same).sum() + cross_repeats.sum()),
    )


def propose_thresholds(scores: LanguageScores, current: MatchThresholds) -> MatchThresholds:
    """Searches each threshold for the safest value that does the most good.

    Args:
        scores: One language's scores.
        current: The thresholds in use; `top_k` is kept.

    Returns:
        MatchThresholds: zero wrong matches, zero false guard flags and zero false repeats,
        each maximising what it catches; ties go to the stricter value.
    """
    accept, margin = _propose_accept_margin(scores)
    return MatchThresholds(
        accept=accept,
        margin=margin,
        reject=_propose_reject(scores, accept),
        guard=_lowest_safe_cutoff(scores.max_guard_score[~scores.expects_guard], current.guard),
        repeat=_lowest_safe_cutoff(
            np.concatenate(
                [scores.pair_similarity[~scores.pair_same], scores.cross_label_similarity]
            ),
            current.repeat,
        ),
        top_k=current.top_k,
    )


def _matched(scores: LanguageScores, accept: float, margin: float) -> np.ndarray:
    """Marks the cases the match rule would answer directly.

    Args:
        scores: One language's scores.
        accept: The minimum best score.
        margin: The minimum lead over the second intent.

    Returns:
        np.ndarray: one boolean per case.
    """
    return (scores.best >= accept) & (scores.best - scores.second >= margin)


def _propose_accept_margin(scores: LanguageScores) -> tuple[float, float]:
    """Sets the margin from the messages that could be matched wrongly, then the safest accept.

    - Only messages scoring within reach of a match matter: at least the lowest right match
      minus twice `MIN_SAFETY_GAP`. Anything lower stays at least one gap below `accept`.
    - `margin`: the largest lead any of those non-catalog (or mis-ranked) messages has over its
      best rival, plus the gap, so none of them can be matched.
    - `accept`: the lowest score among the right matches that clear that margin, minus the gap,
      so all of them are still answered, but no lower.

    Args:
        scores: One language's scores.

    Returns:
        tuple[float, float]: the accept and margin, on the grid.
    """
    right_cases = scores.expects_intent & scores.best_is_expected
    lead = scores.best - scores.second
    lowest_right = scores.best[right_cases].min(initial=float(ACCEPTS[-1]))
    within_reach = ~right_cases & (scores.best >= lowest_right - 2 * MIN_SAFETY_GAP)
    margin = _snap_up(lead[within_reach].max(initial=0.0) + MIN_SAFETY_GAP, MARGINS)
    answered = right_cases & (lead >= margin)
    lowest_answered = scores.best[answered].min(initial=float(ACCEPTS[-1]))
    accept = _snap_down(lowest_answered - MIN_SAFETY_GAP, ACCEPTS)
    return accept, margin


def _snap_up(value: float, grid: np.ndarray) -> float:
    """Rounds a value up to the next grid point.

    Args:
        value: The value.
        grid: The sorted grid.

    Returns:
        float: the smallest grid point at or above the value, or the last point.
    """
    above = grid[grid >= round(value, 2)]
    return float(above[0]) if above.size else float(grid[-1])


def _snap_down(value: float, grid: np.ndarray) -> float:
    """Rounds a value down to the previous grid point.

    Args:
        value: The value.
        grid: The sorted grid.

    Returns:
        float: the largest grid point at or below the value, or the first point.
    """
    below = grid[grid <= round(value, 2)]
    return float(below[-1]) if below.size else float(grid[0])


def _propose_reject(scores: LanguageScores, accept: float) -> float:
    """Finds the highest no-match cutoff that keeps every catalog message above it.

    Below `reject` the customer is asked to rephrase; between `reject` and `accept` they are
    offered the candidates, which is the better reply for a message that belongs to an intent.

    Args:
        scores: One language's scores.
        accept: The chosen match threshold; `reject` stays below it.

    Returns:
        float: the cutoff, from the grid, below which no catalog message falls.
    """
    lowest_catalog = (
        scores.best[scores.expects_intent].min() if scores.expects_intent.any() else accept
    )
    below = GRID[(GRID <= lowest_catalog) & (GRID < accept)]
    return float(below[-1]) if below.size else float(GRID[0])


def _lowest_safe_cutoff(negatives: np.ndarray, current: float) -> float:
    """Finds the lowest cutoff no negative reaches: the one that catches the most positives.

    Args:
        negatives: Scores that must stay below the cutoff (false flags, false repeats).
        current: The value in use, kept when there are no negatives to measure against.

    Returns:
        float: the cutoff from the grid; the strictest value if every cutoff lets one through.
    """
    if negatives.size == 0:
        return current
    for cutoff in GRID:
        if not (negatives >= cutoff).any():
            return float(cutoff)
    return float(GRID[-1])
