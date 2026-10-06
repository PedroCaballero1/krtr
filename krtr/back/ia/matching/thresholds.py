"""Loads the matcher's thresholds for each embedding model and language.

Exists because similarity scores depend on the model and differ between ES and PT, so one set
of thresholds cannot serve them all (docs/ia-proposal.md §3.1). The values live in
`thresholds.json` next to this module and are set from `krtr back ia evaluate`. Consumed by
`engine/factory.py`.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

THRESHOLDS_FILE = Path(__file__).parent / "thresholds.json"

LanguageThresholds = dict[InterfaceLanguage, MatchThresholds]


class ThresholdTable(BaseModel):
    """Every model's thresholds, per language."""

    models: dict[EmbeddingModel, LanguageThresholds]


def load_thresholds(model: EmbeddingModel, path: Path = THRESHOLDS_FILE) -> LanguageThresholds:
    """Returns one model's thresholds, checking that every language has them.

    Args:
        model: The selected embedding model.
        path: The thresholds file.

    Returns:
        LanguageThresholds: the model's thresholds for every supported language.

    Raises:
        ValueError: if the model, or one of its languages, has no thresholds.
    """
    table = ThresholdTable.model_validate({"models": json.loads(path.read_text("utf-8"))})
    by_language = table.models.get(model)
    if by_language is None:
        raise ValueError(f"No thresholds for the embedding model {model.value}")
    missing = [language.value for language in InterfaceLanguage if language not in by_language]
    if missing:
        raise ValueError(f"No {model.value} thresholds for: {', '.join(missing)}")
    return by_language


def save_thresholds(
    model: EmbeddingModel, by_language: LanguageThresholds, path: Path = THRESHOLDS_FILE
) -> None:
    """Replaces one model's thresholds, keeping the other models' untouched.

    Exists for `krtr back ia evaluate --write`, so measured thresholds are applied without
    hand-editing JSON.

    Args:
        model: The model whose thresholds change.
        by_language: The new thresholds for every language.
        path: The thresholds file.

    Returns:
        None.
    """
    raw = json.loads(path.read_text("utf-8"))
    raw[model.value] = {
        language.value: thresholds.model_dump() for language, thresholds in by_language.items()
    }
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
