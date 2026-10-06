"""Builds the facts of the replies that are not an action's answer: questions and endings.

Exists so a question, an escalation or a closure is phrased by the same template writer as an
action's answer, from typed content instead of text. Consumed by `engine/engine.py`.
"""

from krtr.back.ia.artifacts import MessageKey, ReplyContent
from krtr.back.ia.reasoning.artifacts import (
    Closed,
    ClosureReason,
    Escalated,
    EscalationReason,
    NeedsClarification,
    QuestionKind,
)

QUESTION_MESSAGES: dict[QuestionKind, MessageKey] = {
    QuestionKind.CHOOSE_INTENT: MessageKey.ASK_CHOOSE_INTENT,
    QuestionKind.CHOOSE_OPTION: MessageKey.ASK_CHOOSE_OPTION,
    QuestionKind.PROVIDE_SLOT: MessageKey.ASK_PROVIDE_SLOT,
    QuestionKind.REPHRASE: MessageKey.ASK_REPHRASE,
}

CLOSURE_MESSAGES: dict[ClosureReason, MessageKey] = {
    ClosureReason.REPETITIVE: MessageKey.CLOSED_REPETITIVE,
    ClosureReason.AGGRESSIVE: MessageKey.CLOSED_AGGRESSIVE,
    ClosureReason.OFF_TOPIC: MessageKey.CLOSED_OFF_TOPIC,
}

ESCALATION_MESSAGES: dict[EscalationReason, MessageKey] = {
    EscalationReason.CLARIFICATION_LIMIT: MessageKey.ESCALATED,
    EscalationReason.UNSUPPORTED_REQUEST: MessageKey.ESCALATED_UNSUPPORTED,
}


def question_content(resolution: NeedsClarification) -> ReplyContent:
    """Builds a question's facts: the slot asked for and the numbered options.

    Args:
        resolution: The question to ask.

    Returns:
        ReplyContent: the question's message, with one item per option, numbered from 1.
    """
    question = resolution.question
    values = {"slot": question.slot} if question.slot else {}
    items = [
        {"number": str(position), "option": option}
        for position, option in enumerate(question.options, start=1)
    ]
    return ReplyContent(message_key=QUESTION_MESSAGES[question.kind], values=values, items=items)


def ending_content(resolution: Escalated | Closed) -> ReplyContent:
    """Builds the facts of an escalation or a closure.

    Args:
        resolution: How the conversation ends.

    Returns:
        ReplyContent: the matching message.
    """
    if isinstance(resolution, Escalated):
        return ReplyContent(message_key=ESCALATION_MESSAGES[resolution.reason])
    return ReplyContent(message_key=CLOSURE_MESSAGES[resolution.reason])
