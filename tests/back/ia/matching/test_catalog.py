"""Tests that the exemplar catalog loads only complete, known files and scores by best phrase."""

from pathlib import Path

import pytest

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.catalog import ExemplarCatalog
from krtr.back.ia.matching.config import CatalogConfig
from krtr.back.ia.matching.hashing import HashingEmbedder
from krtr.back.ia.matching.labels import GuardLabel
from tests.back.ia.fakes import catalog_of, unit

EMBEDDER = HashingEmbedder()
ONE_PER_LANGUAGE = CatalogConfig(min_exemplars_per_language=1)


def _write_complete_catalog(directory: Path) -> None:
    """Writes one phrase per intent and language, plus a blank line to skip."""
    for language in ("es", "pt-BR"):
        (directory / language).mkdir(parents=True, exist_ok=True)
        for intent in Intent:
            (directory / language / f"{intent.value}.txt").write_text(f"{intent.value}\n\n")


def test_the_shipped_catalog_loads() -> None:
    """The phrases in the repository cover every intent in both languages."""
    catalog = ExemplarCatalog.load(EMBEDDER, CatalogConfig())

    scores = catalog.best_scores(EMBEDDER.embed(["¿Cuál es mi saldo?"])[0])

    assert max(scores, key=scores.__getitem__) == Intent.ACCOUNT_BALANCE


def test_blank_lines_are_not_phrases(tmp_path: Path) -> None:
    """A trailing blank line does not become an empty example that matches everything."""
    _write_complete_catalog(tmp_path)

    catalog = ExemplarCatalog.load(EMBEDDER, ONE_PER_LANGUAGE, tmp_path)

    assert len(catalog.best_scores(EMBEDDER.embed(["saldo"])[0])) == len(Intent)


def test_an_unknown_label_file_fails(tmp_path: Path) -> None:
    """A typo in a file name would silently drop an intent's phrases."""
    _write_complete_catalog(tmp_path)
    (tmp_path / "es" / "acount_balance.txt").write_text("saldo\n")

    with pytest.raises(ValueError, match="acount_balance"):
        ExemplarCatalog.load(EMBEDDER, ONE_PER_LANGUAGE, tmp_path)


def test_an_unknown_language_folder_fails(tmp_path: Path) -> None:
    """Phrases for a language the interface does not offer are a mistake."""
    _write_complete_catalog(tmp_path)
    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "account_balance.txt").write_text("balance\n")

    with pytest.raises(ValueError, match="'en'"):
        ExemplarCatalog.load(EMBEDDER, ONE_PER_LANGUAGE, tmp_path)


def test_an_intent_short_of_phrases_in_a_language_fails(tmp_path: Path) -> None:
    """Every intent must be reachable in Portuguese too (G14)."""
    _write_complete_catalog(tmp_path)
    (tmp_path / "pt-BR" / "complaint_status.txt").unlink()

    with pytest.raises(ValueError, match="pt-BR/complaint_status"):
        ExemplarCatalog.load(EMBEDDER, ONE_PER_LANGUAGE, tmp_path)


def test_a_label_scores_its_most_similar_phrase() -> None:
    """One close phrase is enough: a label's score is its best row, not an average."""
    catalog = catalog_of(
        {
            Intent.ACCOUNT_BALANCE: [unit(1, 0, 0), unit(0, 1, 0)],
            GuardLabel.OFF_TOPIC: [unit(0, 0, 1)],
        }
    )

    scores = catalog.best_scores(unit(1, 0, 0))

    assert scores[Intent.ACCOUNT_BALANCE] == pytest.approx(1.0)
    assert scores[GuardLabel.OFF_TOPIC] == pytest.approx(0.0)
