"""Defines the conversation the LLM reads before a customer's latest message.

Exists so the clarifier, the guard confirmer and the evaluation hand the LLM tasks one typed
transcript: rendered into the prompts as context, and read back for the customer's own words
when an answer is grounded. Consumed by `reasoning/llm/tasks.py`.
"""

from pydantic import BaseModel, Field

from krtr.back.ia.messages.artifacts import MessageSender

# How each sender is named in the prompts.
SENDER_ROLES: dict[MessageSender, str] = {
    MessageSender.CUSTOMER: "Customer",
    MessageSender.AGENT: "Agent",
}
CONTINUATION_INDENT = "\n  "  # Keeps a multi-line reply (a numbered question) under its role.


class TranscriptEntry(BaseModel):
    """One earlier message: who wrote it and what it says."""

    sender: MessageSender
    content: str


class ConversationTranscript(BaseModel):
    """The case's earlier messages, oldest first, without the message being read.

    Exists so a reply such as "the same one as before" can be read against what was said.
    """

    entries: list[TranscriptEntry] = Field(default_factory=list)

    def render(self) -> str:
        """Writes the transcript as one `Role: text` line per message, for a prompt.

        Returns:
            str: the lines, oldest first; empty without messages.
        """
        return "\n".join(_render_entry(entry) for entry in self.entries)

    def customer_texts(self) -> list[str]:
        """Lists what the customer wrote, newest first.

        Exists for grounding: an answer may rest on the customer's words, never on the
        agent's, whose questions list every option.

        Returns:
            list[str]: the customer's messages, newest first.
        """
        return [
            entry.content
            for entry in reversed(self.entries)
            if entry.sender == MessageSender.CUSTOMER
        ]


def _render_entry(entry: TranscriptEntry) -> str:
    """Writes one message as `Role: text`, indenting the lines after the first.

    Args:
        entry: The message.

    Returns:
        str: the message, ready for a prompt.
    """
    content = entry.content.strip().replace("\n", CONTINUATION_INDENT)
    return f"{SENDER_ROLES[entry.sender]}: {content}"
