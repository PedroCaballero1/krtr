"""Defines the `krtr back ia` CLI commands, for trying the conversation engine by hand.

Exists so the agent can be exercised before the web chat endpoint exists: `ask` runs one
message, `chat` keeps a conversation going so the clarification flow can be followed. Both
run on the demo engine (sample data in memory, no Neon) with the models chosen by
`--embedding-model` / `--language-model`, else `KRTR_IA_*_MODEL`, else the defaults. Consumed
by `krtr/cli/back/__init__.py`, which registers `ia_app`.
"""

import logging
from enum import StrEnum
from typing import Annotated

import typer

from krtr.back.ia.artifacts import AgentReply, TurnOutcome, UserTurn
from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.demo import DEMO_CUSTOMER_ID, DEMO_INCIDENT_ID, build_demo_engine
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.ia.language.models import LanguageDetectorModel
from krtr.back.ia.matching.evaluation.artifacts import LanguageReport, OutcomeCounts
from krtr.back.ia.matching.evaluation.runner import apply_proposed_thresholds, run_evaluation
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.reasoning.llm.config import LlmConfig
from krtr.back.ia.reasoning.llm.evaluation.artifacts import TaskOutcome
from krtr.back.ia.reasoning.llm.evaluation.runner import run_llm_evaluation
from krtr.back.ia.reasoning.llm.models import LlmModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

ENDING_OUTCOMES = (TurnOutcome.ESCALATED, TurnOutcome.CLOSED)
LANGUAGE_HELP = "Starting language; a clear message in the other one switches the replies."

EmbeddingModelOption = Annotated[
    EmbeddingModel | None,
    typer.Option("--embedding-model", help="Embedding model; overrides KRTR_IA_EMBEDDING_MODEL."),
]
LlmModelOption = Annotated[
    LlmModel | None,
    typer.Option("--llm-model", help="LLM for doubtful turns; overrides KRTR_IA_LLM_MODEL."),
]
LanguageModelOption = Annotated[
    LanguageDetectorModel | None,
    typer.Option("--language-model", help="Language detector; overrides KRTR_IA_LANGUAGE_MODEL."),
]

ia_app = typer.Typer(
    name="ia", help="Try the conversation agent on sample data.", no_args_is_help=True
)


class ChatCommand(StrEnum):
    """What a `chat` user can type instead of a message."""

    EXIT = "/exit"


@ia_app.command(name="ask")
def ask(
    text: str = typer.Argument(..., help="The customer's message."),
    language: InterfaceLanguage = typer.Option(
        InterfaceLanguage.SPANISH, "--language", "-l", help=LANGUAGE_HELP
    ),
    embedding_model: EmbeddingModelOption = None,
    language_model: LanguageModelOption = None,
    llm_model: LlmModelOption = None,
) -> None:
    """Sends one message to the demo engine and shows the reply.

    Args:
        text: The customer's message.
        language: The language to reply in until a message shows another one.
        embedding_model: The embedding model, if chosen on the command line.
        language_model: The language detector, if chosen on the command line.
        llm_model: The LLM, if chosen on the command line.

    Returns:
        None.
    """
    engine = _engine(_models(embedding_model, language_model, llm_model))
    reply = _send(engine, text, language)
    _show(reply)


@ia_app.command(name="chat")
def chat(
    language: InterfaceLanguage = typer.Option(
        InterfaceLanguage.SPANISH, "--language", "-l", help=LANGUAGE_HELP
    ),
    embedding_model: EmbeddingModelOption = None,
    language_model: LanguageModelOption = None,
    llm_model: LlmModelOption = None,
) -> None:
    """Holds a conversation with the demo engine until it ends or `/exit` is typed.

    Args:
        language: The language to reply in until a message shows another one.
        embedding_model: The embedding model, if chosen on the command line.
        language_model: The language detector, if chosen on the command line.
        llm_model: The LLM, if chosen on the command line.

    Returns:
        None.
    """
    engine = _engine(_models(embedding_model, language_model, llm_model))
    logger.info("Chatting as %s; type %s to leave", DEMO_CUSTOMER_ID, ChatCommand.EXIT.value)
    while True:
        text = typer.prompt(">", prompt_suffix=" ")
        if text.strip() == ChatCommand.EXIT:
            return
        reply = _send(engine, text, language)
        _show(reply)
        if reply.outcome in ENDING_OUTCOMES:
            return


@ia_app.command(name="evaluate")
def evaluate(
    embedding_model: EmbeddingModelOption = None,
    write: bool = typer.Option(False, "--write", help="Save the proposed thresholds."),
) -> None:
    """Measures the embedding model on the evaluation set and proposes thresholds per language.

    Args:
        embedding_model: The embedding model, if chosen on the command line.
        write: When True, writes the proposed thresholds into `thresholds.json`.

    Returns:
        None.
    """
    report = run_evaluation(_models(embedding_model, None, None))
    typer.echo(f"Embedding model: {report.model.value}")
    for language_report in report.languages:
        _show_language_report(language_report)
    if write:
        apply_proposed_thresholds(report)
        typer.echo("Proposed thresholds written to thresholds.json")


@ia_app.command(name="evaluate-llm")
def evaluate_llm(llm_model: LlmModelOption = None) -> None:
    """Measures the LLM on free-form replies and guard confirmations, per language.

    Args:
        llm_model: The LLM, if chosen on the command line.

    Returns:
        None.

    Raises:
        typer.Exit: with code 1, if the LLM is `none` or not converted yet.
    """
    try:
        report = run_llm_evaluation(_models(None, None, llm_model), LlmConfig())
    except (ValueError, FileNotFoundError) as error:
        logger.error("%s", error)
        raise typer.Exit(code=1) from error
    typer.echo(f"LLM: {report.model.value}")
    for language_report in report.languages:
        typer.echo(f"\n[{language_report.language.value}]")
        for outcome in language_report.tasks:
            typer.echo(f"  {_task_line(outcome)}")


def _task_line(outcome: TaskOutcome) -> str:
    """Formats one task's outcome on one line.

    Args:
        outcome: The task's counts and latency.

    Returns:
        str: e.g. "choose_option: right 9/11 · false positives 0 · unavailable 0 · p95 812 ms".
    """
    return (
        f"{outcome.task.value}: right {outcome.right}/{outcome.cases} · "
        f"false positives {outcome.false_positives} · unavailable {outcome.unavailable} · "
        f"p50 {outcome.latency_ms_p50:.0f} ms · p95 {outcome.latency_ms_p95:.0f} ms"
    )


def _show_language_report(report: LanguageReport) -> None:
    """Shows one language's outcomes, now and with the proposed thresholds.

    Args:
        report: The language's evaluation.

    Returns:
        None.
    """
    typer.echo(
        f"\n[{report.language.value}] {report.cases} messages, {report.pairs} repetition pairs, "
        f"embedding p50 {report.embed_ms_p50:.1f} ms, p95 {report.embed_ms_p95:.1f} ms"
    )
    typer.echo(f"  current : {_counts_line(report.current)}")
    typer.echo(f"  proposed: {_counts_line(report.proposed)}")
    typer.echo(f"  proposed thresholds: {report.proposed_thresholds.model_dump()}")


def _counts_line(counts: OutcomeCounts) -> str:
    """Formats outcome counts on one line.

    Args:
        counts: The outcomes.

    Returns:
        str: e.g. "right 14 · wrong 0 · ambiguous 3 · no match 2 · guards 9/0 · repeats 4/0".
    """
    return (
        f"right {counts.matched_right} · wrong {counts.matched_wrong} · "
        f"ambiguous {counts.ambiguous} · no match {counts.no_match} · "
        f"guards {counts.guard_right}/{counts.guard_false} false · "
        f"repeats {counts.repeat_caught}/{counts.repeat_false} false"
    )


def _engine(models: IaModelsConfig) -> ConversationEngine:
    """Builds the demo engine, exiting cleanly if a selected model isn't available.

    Args:
        models: The selected models.

    Returns:
        ConversationEngine: the demo engine.

    Raises:
        typer.Exit: with code 1, if the selected LLM hasn't been converted yet.
    """
    try:
        return build_demo_engine(models)
    except FileNotFoundError as error:
        logger.error("%s (or pass --llm-model none)", error)
        raise typer.Exit(code=1) from error


def _models(
    embedding_model: EmbeddingModel | None,
    language_model: LanguageDetectorModel | None,
    llm_model: LlmModel | None,
) -> IaModelsConfig:
    """Resolves the models: the command line first, then the environment, then the defaults.

    Args:
        embedding_model: The `--embedding-model` option, if given.
        language_model: The `--language-model` option, if given.
        llm_model: The `--llm-model` option, if given.

    Returns:
        IaModelsConfig: the validated selection.

    Raises:
        typer.Exit: with code 1, if an environment variable names an unknown model.
    """
    try:
        return IaModelsConfig.resolve(embedding_model, language_model, llm_model)
    except ValueError as error:
        logger.error("%s", error)
        raise typer.Exit(code=1) from error


def _send(engine: ConversationEngine, text: str, language: InterfaceLanguage) -> AgentReply:
    """Sends one message of the demo customer's demo case.

    Args:
        engine: The demo engine.
        text: The customer's message.
        language: The language to reply in until a message shows another one.

    Returns:
        AgentReply: the engine's reply.

    Raises:
        typer.BadParameter: if the message is blank.
    """
    if not text.strip():
        raise typer.BadParameter("The message cannot be empty.")
    turn = UserTurn(
        incident_id=DEMO_INCIDENT_ID, customer_id=DEMO_CUSTOMER_ID, text=text, language=language
    )
    return engine.handle(turn)


def _show(reply: AgentReply) -> None:
    """Shows the reply, how the turn ended and how long it took.

    The per-step durations are logged at debug level (`krtr --verbose back ia ...`).

    Args:
        reply: The engine's reply.

    Returns:
        None.
    """
    typer.echo(f"[{reply.outcome.value} · {reply.timings.total_ms:.2f} ms] {reply.reply}")
