"""Defines the guard labels: example sets that flag a message instead of answering it.

Exists so the catalog can hold, next to the intents, phrases that look aggressive, off-topic,
or like banking requests the agent can't answer, and one embedding scores them all. They are
also the intents' rivals: a match needs a clear lead over them, not only over the second
intent. Consumed by `matching/` and `guardrails/`.
"""

from enum import StrEnum


class GuardLabel(StrEnum):
    """A kind of message the G13 hard rules look for.

    Exists so the exemplar files of the guardrails are validated like the intents'. A guard
    match only flags the message; closing on it needs the LLM's confirmation (phase 3).
    """

    AGGRESSIVE = "aggressive"
    OFF_TOPIC = "off_topic"
    UNSUPPORTED = "unsupported"  # Banking requests the agent can't answer (a person must).
