"""Defines the `krtr back ia` CLI commands, for trying the conversation engine by hand.

Exists so the agent can be exercised before the web chat endpoint exists: `ask` runs one
message, `chat` keeps a conversation going so the clarification flow can be followed. Both
run on the demo engine (sample data, no network, no model). Consumed by
`krtr/cli/back/__init__.py`, which registers `ia_app`.
"""

import logging
from enum import StrEnum

import typer

from krtr.back.ia.artifacts import AgentReply, TurnOutcome, UserTurn
from krtr.back.ia.demo import DEMO_CUSTOMER_ID, DEMO_INCIDENT_ID, build_demo_engine
from krtr.back.ia.engine.engine import ConversationEngine
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

ENDING_OUTCOMES = (TurnOutcome.ESCALATED, TurnOutcome.CLOSED)
LANGUAGE_HELP = "Starting language; a clear message in the other one switches the replies."

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
) -> None:
    """Sends one message to the demo engine and shows the reply.

    Args:
        text: The customer's message.
        language: The language to reply in until a message shows another one.

    Returns:
        None.
    """
    reply = _send(build_demo_engine(), text, language)
    _show(reply)


@ia_app.command(name="chat")
def chat(
    language: InterfaceLanguage = typer.Option(
        InterfaceLanguage.SPANISH, "--language", "-l", help=LANGUAGE_HELP
    ),
) -> None:
    """Holds a conversation with the demo engine until it ends or `/exit` is typed.

    Args:
        language: The language to reply in until a message shows another one.

    Returns:
        None.
    """
    engine = build_demo_engine()
    logger.info("Chatting as %s; type %s to leave", DEMO_CUSTOMER_ID, ChatCommand.EXIT.value)
    while True:
        text = typer.prompt(">", prompt_suffix=" ")
        if text.strip() == ChatCommand.EXIT:
            return
        reply = _send(engine, text, language)
        _show(reply)
        if reply.outcome in ENDING_OUTCOMES:
            return


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
    """Shows the reply and how the turn ended.

    Args:
        reply: The engine's reply.

    Returns:
        None.
    """
    typer.echo(f"[{reply.outcome.value}] {reply.reply}")
