"""Defines the evaluation set and the report `krtr back ia evaluate` produces.

Exists so the labelled messages, the repetition pairs and the measured outcomes are typed
contracts shared by the loader, the scorer, the threshold search and the CLI.
"""

from enum import StrEnum

from pydantic import BaseModel

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

NO_INTENT_LABEL = "none"  # File name of the messages that must match no intent and no guard.
REPETITION_FILE = "repetition.tsv"


class PairKind(StrEnum):
    """Whether two messages are the same request (a repeat) or different ones."""

    SAME = "same"
    DIFFERENT = "different"  # E.g. the same request for another product: a new question.


class EvaluationCase(BaseModel):
    """One labelled message: the intent or guard it must reach, or None for neither."""

    language: InterfaceLanguage
    expected: Intent | GuardLabel | None
    text: str


class RepetitionPair(BaseModel):
    """Two messages and whether the second repeats the first."""

    language: InterfaceLanguage
    kind: PairKind
    first: str
    second: str


class EvaluationSet(BaseModel):
    """Every labelled message and repetition pair, in every language."""

    cases: list[EvaluationCase]
    pairs: list[RepetitionPair]


class OutcomeCounts(BaseModel):
    """What a set of thresholds does to one language's evaluation set."""

    matched_right: int  # Answered with the expected intent.
    matched_wrong: int  # Answered with another intent, or answered a message that has none.
    ambiguous: int
    no_match: int
    guard_right: int  # Guard messages flagged.
    guard_false: int  # Intent or `none` messages flagged.
    repeat_caught: int  # `same` pairs counted as repeats.
    repeat_false: int  # `different` pairs, or messages with different labels, counted as repeats.


class LanguageReport(BaseModel):
    """One language's results with the current thresholds and with the proposed ones."""

    language: InterfaceLanguage
    cases: int
    pairs: int
    current: OutcomeCounts
    proposed: OutcomeCounts
    proposed_thresholds: MatchThresholds
    embed_ms_p50: float
    embed_ms_p95: float


class EvaluationReport(BaseModel):
    """The full evaluation of one embedding model.

    Exists as the return contract of `run_evaluation`, rendered by `krtr back ia evaluate`.
    """

    model: EmbeddingModel
    languages: list[LanguageReport]
