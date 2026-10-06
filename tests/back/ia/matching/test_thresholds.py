"""Tests loading and saving the thresholds per model and language."""

import json
from pathlib import Path

import pytest

from krtr.back.ia.matching.config import MatchThresholds
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.matching.thresholds import THRESHOLDS_FILE, load_thresholds, save_thresholds
from krtr.back.security.oidc.artifacts import InterfaceLanguage


def _write(path: Path, raw: dict) -> Path:
    path.write_text(json.dumps(raw))
    return path


def test_the_shipped_file_covers_every_model_and_language() -> None:
    """Any model selectable by the Enum can build an engine in either language."""
    for model in EmbeddingModel:
        assert set(load_thresholds(model)) == set(InterfaceLanguage)


def test_a_model_without_thresholds_fails(tmp_path: Path) -> None:
    """Running a model with another model's thresholds would be silently wrong."""
    path = _write(tmp_path / "t.json", {"hashing": {"es": {}, "pt-BR": {}}})

    with pytest.raises(ValueError, match="multilingual_minilm"):
        load_thresholds(EmbeddingModel.MULTILINGUAL_MINILM, path)


def test_a_language_without_thresholds_fails(tmp_path: Path) -> None:
    """A Portuguese conversation would crash mid-way instead of at startup."""
    path = _write(tmp_path / "t.json", {"hashing": {"es": {}}})

    with pytest.raises(ValueError, match="pt-BR"):
        load_thresholds(EmbeddingModel.HASHING, path)


def test_saving_one_model_keeps_the_others(tmp_path: Path) -> None:
    """`evaluate --write` for MiniLM must not touch the hashing values."""
    path = _write(tmp_path / "t.json", json.loads(THRESHOLDS_FILE.read_text()))
    hashing_before = load_thresholds(EmbeddingModel.HASHING, path)
    new = {language: MatchThresholds(accept=0.9, reject=0.5) for language in InterfaceLanguage}

    save_thresholds(EmbeddingModel.MULTILINGUAL_MINILM, new, path)

    assert load_thresholds(EmbeddingModel.MULTILINGUAL_MINILM, path) == new
    assert load_thresholds(EmbeddingModel.HASHING, path) == hashing_before
