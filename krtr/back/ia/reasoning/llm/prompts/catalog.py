"""Loads the LLM prompt templates, one plain-text file per task.

Exists so the instructions given to the model can be reviewed and edited as text, like the
catalog phrases, and a missing template fails when the engine is built. Consumed by
`reasoning/llm/tasks.py`.
"""

from enum import StrEnum
from pathlib import Path

PROMPTS_DIRECTORY = Path(__file__).parent
PROMPT_SUFFIX = ".txt"


class PromptName(StrEnum):
    """The tasks the LLM is asked to do, each with its template file."""

    CHOOSE_OPTION = "choose_option"  # Read a free-form reply against the offered options.
    EXTRACT_VALUE = "extract_value"  # Find a free slot (e.g. a complaint ID) in the text.
    CONFIRM_GUARD = "confirm_guard"  # Confirm an aggressive / off-topic flag before closing.


class PromptCatalog:
    """The prompt templates, read once.

    Exists so a template is loaded and checked at startup, not on the first doubtful turn.
    """

    def __init__(self, templates: dict[PromptName, str]) -> None:
        """Keeps the templates.

        Args:
            templates: One template per prompt name.
        """
        self._templates = templates

    @classmethod
    def load(cls, directory: Path = PROMPTS_DIRECTORY) -> "PromptCatalog":
        """Reads every template, failing fast on a missing one.

        Args:
            directory: The folder holding `<name>.txt`.

        Returns:
            PromptCatalog: the templates.

        Raises:
            FileNotFoundError: if a prompt name has no template file.
        """
        return cls(
            {
                name: (directory / f"{name.value}{PROMPT_SUFFIX}").read_text("utf-8")
                for name in PromptName
            }
        )

    def render(self, name: PromptName, **values: str) -> str:
        """Fills a template with the turn's values.

        Args:
            name: The task.
            **values: The template's placeholders.

        Returns:
            str: the prompt to send.

        Raises:
            KeyError: if a placeholder has no value.
        """
        return self._templates[name].format(**values)
