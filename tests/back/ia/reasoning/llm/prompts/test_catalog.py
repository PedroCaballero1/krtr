"""Tests that every prompt template loads and fills with the values its task gives it."""

from pathlib import Path

import pytest

from krtr.back.ia.reasoning.llm.prompts.catalog import PromptCatalog, PromptName

VALUES = {
    PromptName.CHOOSE_OPTION: {
        "language": "Spanish",
        "conversation": "c",
        "question": "q",
        "options": "o",
        "reply": "r",
    },
    PromptName.EXTRACT_VALUE: {
        "language": "Spanish",
        "conversation": "c",
        "slot": "s",
        "reply": "r",
    },
    PromptName.CONFIRM_GUARD: {"language": "Spanish", "conversation": "c", "reply": "r"},
}


@pytest.mark.parametrize("name", list(PromptName))
def test_every_template_fills_with_exactly_its_task_values(name: PromptName) -> None:
    """A placeholder the task doesn't send would crash the doubtful turn."""
    rendered = PromptCatalog.load().render(name, **VALUES[name])

    assert "{" not in rendered and "}" not in rendered


def test_a_missing_template_fails_when_loaded(tmp_path: Path) -> None:
    """Startup fails, not the first doubtful turn."""
    with pytest.raises(FileNotFoundError):
        PromptCatalog.load(tmp_path)
