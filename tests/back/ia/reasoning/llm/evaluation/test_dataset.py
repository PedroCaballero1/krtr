"""Tests loading the LLM evaluation: reply lines, and confirmation cases derived from guards."""

from pathlib import Path

import pytest

from krtr.back.ia.matching.evaluation.artifacts import EvaluationCase, EvaluationSet
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.reasoning.llm.evaluation.artifacts import LlmTask
from krtr.back.ia.reasoning.llm.evaluation.dataset import load_llm_cases
from krtr.back.security.oidc.artifacts import InterfaceLanguage

SPANISH = InterfaceLanguage.SPANISH


def _guards(*pairs: tuple[GuardLabel | None, str]) -> EvaluationSet:
    cases = [EvaluationCase(language=SPANISH, expected=label, text=text) for label, text in pairs]
    return EvaluationSet(cases=cases, pairs=[])


def test_reply_lines_become_cases_with_their_options(tmp_path: Path) -> None:
    """Options are comma-separated; an empty field means a free slot."""
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "replies.tsv").write_text(
        "choose_option\tproduct_type\ta,b\tla b\tb\nextract_value\tcomplaint_id\t\tPQR-1\tPQR-1\n"
    )

    cases = load_llm_cases(_guards(), tmp_path)

    assert [(c.task, c.options, c.expected) for c in cases] == [
        (LlmTask.CHOOSE_OPTION, ["a", "b"], "b"),
        (LlmTask.EXTRACT_VALUE, [], "PQR-1"),
    ]


def test_guard_messages_must_be_confirmed_and_unsupported_ones_must_not(tmp_path: Path) -> None:
    """An angry banking complaint confirmed as abusive would close a real customer's case."""
    matcher_set = _guards(
        (GuardLabel.AGGRESSIVE, "inútiles"),
        (GuardLabel.UNSUPPORTED, "me cobraron de más"),
        (None, "gracias"),
    )

    cases = load_llm_cases(matcher_set, tmp_path)

    assert {(c.subject, c.reply, c.expected) for c in cases} == {
        ("aggressive", "inútiles", "true"),
        ("aggressive", "me cobraron de más", "false"),
        ("off_topic", "me cobraron de más", "false"),
    }


def test_a_malformed_line_fails(tmp_path: Path) -> None:
    """A line with a missing field would silently drop a case."""
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "replies.tsv").write_text("choose_option\tproduct_type\tla b\n")

    with pytest.raises(ValueError, match="5 or 6 tab-separated fields"):
        load_llm_cases(_guards(), tmp_path)


def test_the_shipped_replies_cover_both_languages_and_every_task() -> None:
    """Each language has reply cases, including replies that must get `none`."""
    cases = load_llm_cases(_guards())

    for language in InterfaceLanguage:
        tasks = {c.task for c in cases if c.language == language}
        assert {LlmTask.CHOOSE_OPTION, LlmTask.EXTRACT_VALUE} <= tasks
        assert any(c.expected == "none" for c in cases if c.language == language)


def test_a_sixth_field_is_the_cases_history_with_its_line_breaks(tmp_path: Path) -> None:
    """`customer: … || agent: …` entries, oldest first; a literal backslash-n breaks a line."""
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "replies.tsv").write_text(
        "choose_option\tproduct_type\ta,b\tesa\tb\t"
        "customer: mi b || agent: ¿Cuál?\\n1. a\\n2. b\n"
        "choose_option\tproduct_type\ta,b\tla b\tb\n"
    )

    with_history, without_history = load_llm_cases(_guards(), tmp_path)

    assert [(e.sender, e.content) for e in with_history.history.entries] == [
        (MessageSender.CUSTOMER, "mi b"),
        (MessageSender.AGENT, "¿Cuál?\n1. a\n2. b"),
    ]
    assert without_history.history.entries == []


@pytest.mark.parametrize("entry", ["mi b", "robot: mi b"])
def test_a_history_entry_without_a_known_sender_fails(tmp_path: Path, entry: str) -> None:
    """A typo in the sender would silently turn a customer's words into nobody's."""
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "replies.tsv").write_text(
        f"choose_option\tproduct_type\ta\tesa\ta\t{entry}\n"
    )

    with pytest.raises(ValueError):
        load_llm_cases(_guards(), tmp_path)
