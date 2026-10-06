"""Runs the LLM evaluation: each case through the real tasks, timed and scored.

Exists so the LLM's accuracy, its riskiest errors (answering when it should say `none`, or
confirming a closure that isn't deserved) and its latency are measured on the same prompts
and schemas the engine uses (Q3-A, Q3-C). Consumed by `krtr back ia evaluate-llm`.
"""

import logging
import time

import numpy as np

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.deterministic.base import DeterministicAction
from krtr.back.ia.deterministic.config import DeterministicConfig
from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.deterministic.readers import InMemoryComplaintsReader, InMemoryProductsReader
from krtr.back.ia.engine.factory import build_actions
from krtr.back.ia.matching.evaluation.dataset import load_evaluation_set
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.llm.base import MeteredLlmClient
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.evaluation.artifacts import (
    NO_ANSWER,
    LlmCase,
    LlmEvaluationReport,
    LlmLanguageReport,
    LlmTask,
    TaskOutcome,
)
from krtr.back.ia.reasoning.llm.evaluation.dataset import CONFIRMED, NOT_CONFIRMED, load_llm_cases
from krtr.back.ia.reasoning.llm.factory import build_llm_client
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog
from krtr.back.ia.reasoning.llm.tasks import LlmTasks
from krtr.back.ia.writing.templates.writer import TemplateResponseWriter
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

MILLISECONDS_PER_SECOND = 1000
P95 = 95


def run_llm_evaluation(models: IaModelsConfig, config: LlmConfig) -> LlmEvaluationReport:
    """Evaluates the selected LLM on every language and task.

    Args:
        models: The selection; the LLM and its cache are used.
        config: The LLM's limits, the same the engine applies.

    Returns:
        LlmEvaluationReport: per language and task, the outcomes and the latency.

    Raises:
        ValueError: if the selected LLM is `none`: there is nothing to evaluate.
    """
    client = build_llm_client(models.llm, models.model_cache, config)
    if client is None:
        raise ValueError("Select an LLM to evaluate (--llm-model); `none` runs no model")
    metered = MeteredLlmClient(client)
    tasks = LlmTasks(metered, PromptCatalog.load(), TemplateResponseWriter.load())
    gates = _slot_gates()
    cases = load_llm_cases(load_evaluation_set())
    languages = [
        LlmLanguageReport(
            language=language,
            tasks=[
                _run_task(
                    tasks,
                    metered,
                    gates,
                    task,
                    [c for c in cases if (c.language, c.task) == (language, task)],
                )
                for task in LlmTask
            ],
        )
        for language in InterfaceLanguage
    ]
    return LlmEvaluationReport(model=models.llm, languages=languages)


def _run_task(
    tasks: LlmTasks,
    metered: MeteredLlmClient,
    gates: dict[str, DeterministicAction],
    task: LlmTask,
    cases: list[LlmCase],
) -> TaskOutcome:
    """Runs one task's cases and scores them.

    Args:
        tasks: The real LLM tasks.
        metered: The same client, to count unavailability.
        gates: The action that validates each slot, as the agent applies it.
        task: The task.
        cases: Its cases in one language.

    Returns:
        TaskOutcome: the counts and the latency.
    """
    logger.info("Evaluating %s on %d cases", task.value, len(cases))
    metered.reset()
    latencies, right, false_positives = [], 0, 0
    for case in cases:
        started_at = time.perf_counter()
        answer = _answer(tasks, gates, case)
        latencies.append((time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND)
        right += answer == case.expected
        false_positives += case.expected in (NO_ANSWER, NOT_CONFIRMED) and answer != case.expected
    return TaskOutcome(
        task=task,
        cases=len(cases),
        right=right,
        wrong=len(cases) - right,
        false_positives=false_positives,
        unavailable=metered.failures,
        latency_ms_p50=float(np.percentile(latencies, 50)) if latencies else 0.0,
        latency_ms_p95=float(np.percentile(latencies, P95)) if latencies else 0.0,
    )


def _answer(tasks: LlmTasks, gates: dict[str, DeterministicAction], case: LlmCase) -> str:
    """Asks the task the case is about, keeping only what the agent would accept.

    Slot values go through the same path as in the clarifier (`fill_slot`, with its grounding
    check, then the action's `validate_slot`), so the evaluation measures what reaches the
    customer.

    Args:
        tasks: The real LLM tasks.
        gates: The action that validates each slot.
        case: The case.

    Returns:
        str: an option, a value, `none`, or `true` / `false`.
    """
    if case.task == LlmTask.CONFIRM_GUARD:
        confirmed = tasks.confirm_guard(GuardLabel(case.subject), case.reply, case.language)
        return CONFIRMED if confirmed else NOT_CONFIRMED
    gate = gates.get(case.subject)
    if gate is None:
        answer = tasks.choose_option(case.subject, case.options, case.reply, case.language)
        return answer or NO_ANSWER
    answer = tasks.fill_slot(case.subject, case.options, case.reply, case.language)
    if answer:
        answer = gate.validate_slot(case.subject, answer)
    return answer or NO_ANSWER


def _slot_gates() -> dict[str, DeterministicAction]:
    """Maps every slot to the action whose rules validate it.

    Returns:
        dict[str, DeterministicAction]: e.g. `{"complaint_id": ComplaintStatusAction}`.
    """
    actions = build_actions(
        InMemoryProductsReader({}), InMemoryComplaintsReader({}), DeterministicConfig()
    )
    return {
        str(slot): actions.get(intent)
        for intent in Intent
        for slot in actions.get(intent).slots_model.model_fields
    }
