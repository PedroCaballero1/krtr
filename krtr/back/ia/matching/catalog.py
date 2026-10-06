"""Loads the example phrases of every intent and guard label, embedded once, into memory.

Exists so each message is compared against a precomputed matrix instead of re-embedding the
examples per turn. The phrases live in `exemplars/<language>/<label>.txt`, one per line: the
cheapest format for an LLM to read or write, parsed with `splitlines()`. Consumed by
`matching/matcher.py` and `engine/factory.py`.
"""

import logging
from pathlib import Path

import numpy as np

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.base import Embedder
from krtr.back.ia.matching.config import CatalogConfig
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

EXEMPLARS_DIRECTORY = Path(__file__).parent / "exemplars"
EXEMPLAR_SUFFIX = ".txt"

CatalogLabel = Intent | GuardLabel
ExemplarSet = dict[tuple[InterfaceLanguage, CatalogLabel], list[str]]


class ExemplarCatalog:
    """The embedded example phrases, one row per phrase, with the label each row belongs to.

    Exists so the matcher can score a message against every label with one matrix product.
    Built with `ExemplarCatalog.load`.
    """

    def __init__(self, labels: list[CatalogLabel], matrix: np.ndarray) -> None:
        """Keeps the rows and their labels.

        Args:
            labels: The label of each row of `matrix`.
            matrix: The L2-normalised embedding of each example phrase.
        """
        self._labels = labels
        self._matrix = matrix

    @classmethod
    def load(
        cls, embedder: Embedder, config: CatalogConfig, directory: Path = EXEMPLARS_DIRECTORY
    ) -> "ExemplarCatalog":
        """Reads, validates and embeds every exemplar file.

        Args:
            embedder: Embeds the phrases.
            config: The minimum coverage each intent needs.
            directory: The folder holding one subfolder per language.

        Returns:
            ExemplarCatalog: the embedded catalog.

        Raises:
            ValueError: on an unknown language or label, or an intent short of examples.
        """
        exemplars = _read_exemplars(directory)
        _check_coverage(exemplars, config.min_exemplars_per_language)
        labels = [label for (_, label), phrases in exemplars.items() for _ in phrases]
        phrases = [phrase for group in exemplars.values() for phrase in group]
        logger.info("Embedding %d example phrases from %s", len(phrases), directory)
        return cls(labels, embedder.embed(phrases))

    def best_scores(self, vector: np.ndarray) -> dict[CatalogLabel, float]:
        """Scores a message against every label: its most similar example phrase.

        Args:
            vector: The message's L2-normalised embedding.

        Returns:
            dict[CatalogLabel, float]: the best cosine similarity of each label.
        """
        similarities = self._matrix @ vector
        scores: dict[CatalogLabel, float] = {}
        for label, similarity in zip(self._labels, similarities, strict=True):
            scores[label] = max(scores.get(label, -1.0), float(similarity))
        return scores


def _read_exemplars(directory: Path) -> ExemplarSet:
    """Reads every `<language>/<label>.txt` file, skipping blank lines.

    Args:
        directory: The folder holding one subfolder per language.

    Returns:
        ExemplarSet: the phrases of each (language, label).

    Raises:
        ValueError: if a folder is not a known language or a file is not a known label.
    """
    exemplars: ExemplarSet = {}
    for path in sorted(directory.glob(f"*/*{EXEMPLAR_SUFFIX}")):
        language = _parse_language(path.parent.name)
        lines = path.read_text(encoding="utf-8").splitlines()
        exemplars[(language, _parse_label(path.stem))] = [
            line.strip() for line in lines if line.strip()
        ]
    return exemplars


def _parse_language(name: str) -> InterfaceLanguage:
    """Maps a folder name to its language.

    Args:
        name: The folder name, e.g. "pt-BR".

    Returns:
        InterfaceLanguage: the language.

    Raises:
        ValueError: if the folder is not a supported language.
    """
    try:
        return InterfaceLanguage(name)
    except ValueError as error:
        raise ValueError(f"Exemplar folder {name!r} is not a supported language") from error


def _parse_label(stem: str) -> CatalogLabel:
    """Maps a file name to its intent or guard label.

    Args:
        stem: The file name without its suffix, e.g. "account_balance".

    Returns:
        CatalogLabel: the intent or guard label.

    Raises:
        ValueError: if the name is neither.
    """
    for label_type in (Intent, GuardLabel):
        if stem in label_type._value2member_map_:
            return label_type(stem)
    raise ValueError(f"Exemplar file {stem!r} is neither an Intent nor a GuardLabel")


def _check_coverage(exemplars: ExemplarSet, min_exemplars: int) -> None:
    """Checks that every intent has enough phrases in every language.

    Guard labels are optional: without phrases, they simply never flag.

    Args:
        exemplars: The phrases read.
        min_exemplars: The minimum per intent and language.

    Raises:
        ValueError: listing every (language, intent) short of phrases.
    """
    short = [
        f"{language.value}/{intent.value}"
        for language in InterfaceLanguage
        for intent in Intent
        if len(exemplars.get((language, intent), [])) < min_exemplars
    ]
    if short:
        raise ValueError(f"Fewer than {min_exemplars} example phrases for: {', '.join(short)}")
