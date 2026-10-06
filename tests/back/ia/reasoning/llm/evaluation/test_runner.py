"""Tests scoring the LLM evaluation on a scripted model."""

import pytest

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.messages.artifacts import MessageSender
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.evaluation import runner
from krtr.back.ia.reasoning.llm.evaluation.artifacts import LlmCase, LlmTask
from krtr.back.ia.reasoning.llm.models import LlmModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from tests.back.ia.reasoning.llm.fakes import UNAVAILABLE, ScriptedLlm, transcript

SPANISH = InterfaceLanguage.SPANISH
CASES = [
    LlmCase(
        language=SPANISH,
        task=LlmTask.CHOOSE_OPTION,
        subject="request",
        options=["a", "b"],
        reply="la b",
        expected="b",
    ),
    LlmCase(
        language=SPANISH,
        task=LlmTask.CHOOSE_OPTION,
        subject="request",
        options=["a", "b"],
        reply="eh",
        expected="none",
    ),
    LlmCase(
        language=SPANISH,
        task=LlmTask.CHOOSE_OPTION,
        subject="request",
        options=["a", "b"],
        reply="la a",
        expected="a",
    ),
]


def test_scores_count_right_answers_false_positives_and_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answering "a" where `none` was expected is a false positive; a timeout is unavailable."""
    llm = ScriptedLlm({"choice": "b"}, {"choice": "a"}, UNAVAILABLE)
    monkeypatch.setattr(runner, "build_llm_client", lambda *args: llm)
    monkeypatch.setattr(runner, "load_llm_cases", lambda matcher_set: CASES)

    report = runner.run_llm_evaluation(
        IaModelsConfig(llm=LlmModel.QWEN2_5_1_5B_INSTRUCT), LlmConfig()
    )

    spanish = next(item for item in report.languages if item.language == SPANISH)
    choose = next(item for item in spanish.tasks if item.task == LlmTask.CHOOSE_OPTION)
    assert (choose.cases, choose.right, choose.false_positives, choose.unavailable) == (3, 1, 1, 1)


def test_none_cannot_be_evaluated() -> None:
    """There is no model to measure."""
    with pytest.raises(ValueError, match="none"):
        runner.run_llm_evaluation(IaModelsConfig(llm=LlmModel.NONE), LlmConfig())


def test_guard_and_slot_cases_are_read_with_their_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each case's history reaches the prompt, on the guard and the slot paths too."""
    history = transcript((MessageSender.CUSTOMER, "mi queja es la PQR-104233"))
    cases = [
        LlmCase(
            language=SPANISH,
            task=LlmTask.CONFIRM_GUARD,
            subject="aggressive",
            options=[],
            reply="son unos inútiles",
            expected="false",
            history=history,
        ),
        LlmCase(
            language=SPANISH,
            task=LlmTask.EXTRACT_VALUE,
            subject="complaint_id",
            options=[],
            reply="la que te di",
            expected="PQR-104233",
            history=history,
        ),
    ]
    llm = ScriptedLlm({"value": "PQR-104233"}, {"category": "banking"})  # Tasks in enum order.
    monkeypatch.setattr(runner, "build_llm_client", lambda *args: llm)
    monkeypatch.setattr(runner, "load_llm_cases", lambda matcher_set: cases)

    report = runner.run_llm_evaluation(
        IaModelsConfig(llm=LlmModel.QWEN2_5_1_5B_INSTRUCT), LlmConfig()
    )

    spanish = next(item for item in report.languages if item.language == SPANISH)
    right = {item.task: item.right for item in spanish.tasks}
    assert (right[LlmTask.CONFIRM_GUARD], right[LlmTask.EXTRACT_VALUE]) == (1, 1)
    assert all("Customer: mi queja es la PQR-104233" in prompt for prompt in llm.prompts)
