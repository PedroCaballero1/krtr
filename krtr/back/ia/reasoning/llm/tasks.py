"""The three questions the agent may ask the LLM, each one closed and each one with a fallback.

Exists so every LLM use is a narrow, schema-constrained task:
- choosing one of the **offered** options from a free-form reply;
- finding a free slot that **appears literally** in the text;
- confirming a guard flag with yes or no.

The model can never return an intent or a value it wasn't offered. If it can't answer
(`LlmUnavailable`), each task returns "no answer" and the caller keeps the deterministic
behaviour. Consumed by `reasoning/llm/clarifier.py` and `guardrails/`.
"""

import logging
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, create_model

from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.ia.reasoning.llm.base import LlmClient, LlmUnavailable
from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog, PromptName
from krtr.back.ia.text import normalize_text
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

NO_OPTION = "none"  # What the model returns when the reply chooses no offered option.
STEM_LENGTH = 5  # Words compared by their first letters: "ahorro" and "ahorros" share "ahorr".

LANGUAGE_NAMES: dict[InterfaceLanguage, str] = {
    InterfaceLanguage.SPANISH: "Spanish",
    InterfaceLanguage.PORTUGUESE: "Brazilian Portuguese",
}

# Forbidding extra keys makes the guided JSON stop at the answer: no free-text "reason" field
# that runs out of tokens and leaves the JSON unfinished.
STRICT = ConfigDict(extra="forbid")


class MessageCategory(StrEnum):
    """What a flagged message is, as the LLM classifies it before a closure."""

    BANKING = "banking"  # Anything about the customer's money or the bank, angry or not.
    ABUSIVE = "abusive"  # Insults or threats, with no banking request.
    OFF_TOPIC = "off_topic"  # Nothing to do with banking.


# The category that confirms each closing flag; any other answer leaves the case open.
CONFIRMING_CATEGORY: dict[GuardLabel, MessageCategory] = {
    GuardLabel.AGGRESSIVE: MessageCategory.ABUSIVE,
    GuardLabel.OFF_TOPIC: MessageCategory.OFF_TOPIC,
}


class LabelLookup(Protocol):
    """Shows a value in the customer's language. Implemented by `TemplateResponseWriter`."""

    def label(self, value: str, language: InterfaceLanguage) -> str:
        """Returns how a value is shown in a language.

        Args:
            value: An enum value.
            language: The customer's language.

        Returns:
            str: its label.
        """
        ...


class ExtractedValue(BaseModel):
    """The LLM's answer to "find the slot": the text as written, or null."""

    model_config = STRICT

    value: str | None


class CategoryAnswer(BaseModel):
    """The LLM's classification of a flagged message.

    A classification instead of a yes/no: small models asked "is this abusive?" lean to yes,
    and a banking complaint confirmed as abusive would close a real customer's case.
    """

    model_config = STRICT

    category: MessageCategory


class LlmTasks:
    """Runs the three closed tasks against one client.

    Exists so prompts, schemas and fallbacks live in one place. Built by
    `reasoning/llm/factory.py`.
    """

    def __init__(self, client: LlmClient, prompts: PromptCatalog, labels: LabelLookup) -> None:
        """Keeps the client, the prompt templates and the labels of the options.

        Args:
            client: The LLM.
            prompts: The task templates.
            labels: How options are shown to the customer, reused in the prompts.
        """
        self._client = client
        self._prompts = prompts
        self._labels = labels

    def choose_option(
        self, subject: str, options: list[str], reply: str, language: InterfaceLanguage
    ) -> str | None:
        """Reads a free-form reply as one of the offered options.

        Args:
            subject: What was asked about, e.g. "product_type" or "request".
            options: The option codes offered, in order.
            reply: The customer's reply.
            language: The customer's language.

        Returns:
            str | None: the chosen option code, or None if the reply chooses none of them.
        """
        schema = create_model(
            "OptionChoice", __config__=STRICT, choice=(Literal[(*options, NO_OPTION)], ...)
        )
        lines = "\n".join(f"- {code}: {self._labels.label(code, language)}" for code in options)
        prompt = self._prompts.render(
            PromptName.CHOOSE_OPTION,
            language=LANGUAGE_NAMES[language],
            question=f"which {self._labels.label(subject, language)} they mean",
            options=lines,
            reply=reply,
        )
        answer = self._ask(prompt, schema)
        choice = getattr(answer, "choice", NO_OPTION) if answer else NO_OPTION
        return None if choice == NO_OPTION else choice

    def extract_value(self, slot: str, reply: str, language: InterfaceLanguage) -> str | None:
        """Finds a free slot's value, accepting it only if the customer actually wrote it.

        Args:
            slot: The slot's name, e.g. "complaint_id".
            reply: The customer's text.
            language: The customer's language.

        Returns:
            str | None: the value, upper-cased like the rule-based extractors, or None.
        """
        prompt = self._prompts.render(
            PromptName.EXTRACT_VALUE,
            language=LANGUAGE_NAMES[language],
            slot=self._labels.label(slot, language),
            reply=reply,
        )
        answer = self._ask(prompt, ExtractedValue)
        value = answer.value.strip() if answer and answer.value else ""
        if not value or normalize_text(value) not in normalize_text(reply):
            return None
        return value.upper()

    def fill_slot(
        self, slot: str, options: list[str], text: str, language: InterfaceLanguage
    ) -> str | None:
        """Fills one slot: an offered option for a closed slot, a literal value for a free one.

        Exists so the resolver (first message) and the clarifier (a reply) fill slots the same
        way.

        Args:
            slot: The slot's name.
            options: The slot's closed options, or empty for a free slot.
            text: The customer's text.
            language: The customer's language.

        Returns:
            str | None: the value, or None.
        """
        if not options:
            return self.extract_value(slot, text, language)
        choice = self.choose_option(slot, options, text, language)
        if choice is None or not self._is_grounded(choice, options, text, language):
            return None
        return choice

    def confirm_guard(self, label: GuardLabel, reply: str, language: InterfaceLanguage) -> bool:
        """Confirms a flag by classifying the message, never by asking "is it X?".

        Args:
            label: The guard label that flagged the message.
            reply: The customer's message.
            language: The customer's language.

        Returns:
            bool: True only if the LLM classifies the message as the flag's category; False
            for `banking`, the other category, or when the LLM can't answer.
        """
        prompt = self._prompts.render(
            PromptName.CONFIRM_GUARD, language=LANGUAGE_NAMES[language], reply=reply
        )
        answer = self._ask(prompt, CategoryAnswer)
        return getattr(answer, "category", None) == CONFIRMING_CATEGORY[label]

    def _is_grounded(
        self, option: str, options: list[str], text: str, language: InterfaceLanguage
    ) -> bool:
        """Checks that the reply points at the chosen option more than at any other.

        Exists because, with similar options, a small model picks one the reply doesn't
        single out: "la de la tarjeta" fits credit and debit cards alike, so choosing either
        is a guess. The chosen option's label must share strictly more word stems with the
        reply than every other offered option's label. The LLM proposes; this confirms.

        Args:
            option: The option the LLM chose.
            options: Every option offered.
            text: The customer's reply.
            language: The customer's language.

        Returns:
            bool: True if the chosen option overlaps the reply strictly more than all others.
        """
        reply = _stems(text)
        chosen = len(_stems(self._labels.label(option, language)) & reply)
        rivals = [
            len(_stems(self._labels.label(other, language)) & reply)
            for other in options
            if other != option
        ]
        return chosen > max(rivals, default=0)

    def _ask(self, prompt: str, schema: type[BaseModel]) -> BaseModel | None:
        """Calls the LLM, turning unavailability into "no answer".

        Args:
            prompt: The rendered prompt.
            schema: The answer's schema.

        Returns:
            BaseModel | None: the answer, or None if the LLM couldn't give one.
        """
        try:
            return self._client.complete(prompt, schema)
        except LlmUnavailable as error:
            logger.warning("LLM unavailable, keeping the deterministic answer: %s", error)
            return None


def _stems(text: str) -> set[str]:
    """Returns the stems of a text's meaningful words (4 letters or more).

    Args:
        text: Any text.

    Returns:
        set[str]: the first `STEM_LENGTH` letters of each normalised word of 4+ letters.
    """
    return {word[:STEM_LENGTH] for word in normalize_text(text).split() if len(word) >= 4}
