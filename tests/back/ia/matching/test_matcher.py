"""Tests the threshold + margin rule on fixed vectors, independent of any embedder."""

import pytest

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.artifacts import MatchKind
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.matching.matcher import IntentMatcher
from tests.back.ia.fakes import catalog_of, unit

THRESHOLDS = MatchThresholds(accept=0.55, reject=0.25, margin=0.05, guard=0.6)
MATCHER = IntentMatcher(
    catalog_of(
        {
            Intent.ACCOUNT_BALANCE: [unit(1, 0, 0)],
            Intent.COMPLAINT_STATUS: [unit(0, 1, 0)],
            GuardLabel.AGGRESSIVE: [unit(0, 0, 1)],
        }
    ),
    THRESHOLDS,
)


def test_a_high_score_with_a_clear_lead_matches() -> None:
    """Only this case may skip clarification and go straight to an action."""
    result = MATCHER.match(unit(1, 0.1, 0))

    assert result.kind == MatchKind.MATCHED
    assert result.best_intent == Intent.ACCOUNT_BALANCE
    assert [candidate.intent for candidate in result.candidates] == [
        Intent.ACCOUNT_BALANCE,
        Intent.COMPLAINT_STATUS,
    ]


def test_a_high_score_without_a_clear_lead_is_ambiguous() -> None:
    """Two close intents both above `accept` must not be decided by a hair."""
    result = MATCHER.match(unit(1, 0.97, 0))

    assert result.candidates[0].score >= THRESHOLDS.accept
    assert result.kind == MatchKind.AMBIGUOUS
    assert result.best_intent is None


def test_a_score_between_reject_and_accept_is_ambiguous() -> None:
    """Plausible but weak: the customer is offered the candidates."""
    result = MATCHER.match(unit(1, 0, 2.2))

    assert THRESHOLDS.reject <= result.candidates[0].score < THRESHOLDS.accept
    assert result.kind == MatchKind.AMBIGUOUS


def test_a_score_below_reject_is_no_match() -> None:
    """Nothing in the catalog resembles the message."""
    result = MATCHER.match(unit(0.1, 0.1, 1))

    assert result.kind == MatchKind.NO_MATCH


@pytest.mark.parametrize(("aggressive", "flagged"), [(1, True), (0, False)])
def test_guard_labels_flag_without_deciding_the_intent(aggressive: float, flagged: bool) -> None:
    """A guard match is reported next to the intent verdict, never instead of it."""
    result = MATCHER.match(unit(1, 0, aggressive))

    assert (GuardLabel.AGGRESSIVE in result.guard_flags) is flagged
    assert result.candidates[0].intent == Intent.ACCOUNT_BALANCE


def test_reject_must_be_below_accept() -> None:
    """Thresholds that overlap would make `AMBIGUOUS` unreachable."""
    with pytest.raises(ValueError, match="reject"):
        MatchThresholds(accept=0.4, reject=0.4)
