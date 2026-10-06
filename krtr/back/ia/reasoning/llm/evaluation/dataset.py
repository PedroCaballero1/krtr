"""Loads the LLM evaluation cases: free-form replies, plus guard confirmations.

Exists so the replies live as `task<TAB>subject<TAB>options<TAB>reply<TAB>expected` lines in
`messages/<language>/replies.tsv` (options comma-separated, empty for free slots). The guard
confirmations reuse the matcher's evaluation set: its aggressive and off-topic messages must be
confirmed, and its `unsupported` banking requests (angry or not) must not, since confirming
one would close a real customer's conversation. Consumed by `reasoning/llm/evaluation/runner.py`.
"""

from pathlib import Path

from krtr.back.ia.matching.evaluation.artifacts import EvaluationSet
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.llm.evaluation.artifacts import LlmCase, LlmTask
from krtr.back.security.oidc.artifacts import InterfaceLanguage

# Not `data/`: the repository ignores every folder with that name (tasks/lessons.md).
REPLIES_DIRECTORY = Path(__file__).parent / "messages"
REPLIES_FILE = "replies.tsv"
REPLY_FIELDS = 5
CONFIRMED, NOT_CONFIRMED = "true", "false"
CLOSING_LABELS = (GuardLabel.AGGRESSIVE, GuardLabel.OFF_TOPIC)


def load_llm_cases(
    matcher_set: EvaluationSet, directory: Path = REPLIES_DIRECTORY
) -> list[LlmCase]:
    """Reads the reply cases and derives the guard-confirmation cases.

    Args:
        matcher_set: The matcher's evaluation set, the source of the confirmation cases.
        directory: The folder holding one subfolder per language.

    Returns:
        list[LlmCase]: every case, in every language.

    Raises:
        ValueError: on a malformed line.
    """
    cases: list[LlmCase] = []
    for language in InterfaceLanguage:
        cases.extend(_read_replies(directory / language.value / REPLIES_FILE, language))
    return cases + _confirmation_cases(matcher_set)


def _read_replies(path: Path, language: InterfaceLanguage) -> list[LlmCase]:
    """Reads one language's reply cases.

    Args:
        path: The `replies.tsv` file.
        language: Its language.

    Returns:
        list[LlmCase]: the cases, empty without a file.

    Raises:
        ValueError: if a line doesn't have the five tab-separated fields.
    """
    if not path.is_file():
        return []
    cases = []
    for line in path.read_text("utf-8").splitlines():
        fields = line.split("\t")
        if not line.strip():
            continue
        if len(fields) != REPLY_FIELDS:
            raise ValueError(f"{path}: expected 5 tab-separated fields, got {line!r}")
        task, subject, options, reply, expected = fields
        cases.append(
            LlmCase(
                language=language,
                task=LlmTask(task),
                subject=subject,
                options=[option for option in options.split(",") if option],
                reply=reply,
                expected=expected,
            )
        )
    return cases


def _confirmation_cases(matcher_set: EvaluationSet) -> list[LlmCase]:
    """Turns guard messages into "must confirm" cases and unsupported ones into "must not".

    Args:
        matcher_set: The matcher's evaluation set.

    Returns:
        list[LlmCase]: one case per closing label for each relevant message.
    """
    cases = []
    for case in matcher_set.cases:
        for label in CLOSING_LABELS:
            if case.expected == label:
                expected = CONFIRMED
            elif case.expected == GuardLabel.UNSUPPORTED:
                expected = NOT_CONFIRMED
            else:
                continue
            cases.append(
                LlmCase(
                    language=case.language,
                    task=LlmTask.CONFIRM_GUARD,
                    subject=label.value,
                    options=[],
                    reply=case.text,
                    expected=expected,
                )
            )
    return cases
