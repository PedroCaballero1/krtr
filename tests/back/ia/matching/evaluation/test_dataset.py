"""Tests loading the evaluation set: labels from file names, pairs from TSV lines."""

from pathlib import Path

import pytest

from krtr.back.ia.deterministic.intents import Intent
from krtr.back.ia.matching.catalog import EXEMPLARS_DIRECTORY
from krtr.back.ia.matching.evaluation.artifacts import PairKind
from krtr.back.ia.matching.evaluation.dataset import load_evaluation_set
from krtr.back.ia.matching.labels import GuardLabel
from krtr.back.security.oidc.artifacts import InterfaceLanguage


def _folder(root: Path, language: str = "es") -> Path:
    folder = root / language
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def test_file_names_set_the_expected_label(tmp_path: Path) -> None:
    """An intent, a guard, and `none` for messages that must reach neither."""
    folder = _folder(tmp_path)
    (folder / "account_balance.txt").write_text("saldo\n\n")
    (folder / "off_topic.txt").write_text("fútbol\n")
    (folder / "none.txt").write_text("gracias\n")

    cases = load_evaluation_set(tmp_path).cases

    assert {(case.expected, case.text) for case in cases} == {
        (Intent.ACCOUNT_BALANCE, "saldo"),
        (GuardLabel.OFF_TOPIC, "fútbol"),
        (None, "gracias"),
    }
    assert {case.language for case in cases} == {InterfaceLanguage.SPANISH}


def test_repetition_pairs_are_read_by_kind(tmp_path: Path) -> None:
    """Each line is kind, first and second, tab-separated."""
    (_folder(tmp_path) / "repetition.tsv").write_text("same\ta\tb\ndifferent\tc\td\n")

    pairs = load_evaluation_set(tmp_path).pairs

    assert [(pair.kind, pair.first, pair.second) for pair in pairs] == [
        (PairKind.SAME, "a", "b"),
        (PairKind.DIFFERENT, "c", "d"),
    ]


def test_a_malformed_pair_line_fails(tmp_path: Path) -> None:
    """A line without three fields would silently drop a pair."""
    (_folder(tmp_path) / "repetition.tsv").write_text("same\tonly one\n")

    with pytest.raises(ValueError, match="kind<TAB>first<TAB>second"):
        load_evaluation_set(tmp_path)


def test_an_unknown_label_file_fails(tmp_path: Path) -> None:
    """A typo in a file name would silently drop its messages."""
    (_folder(tmp_path) / "acount_balance.txt").write_text("saldo\n")

    with pytest.raises(ValueError, match="acount_balance"):
        load_evaluation_set(tmp_path)


def test_the_shipped_set_never_reuses_a_catalog_phrase() -> None:
    """Thresholds set on the catalog's own phrases would look perfect and mean nothing."""
    catalog = {
        line.strip().casefold()
        for path in EXEMPLARS_DIRECTORY.glob("*/*.txt")
        for line in path.read_text("utf-8").splitlines()
        if line.strip()
    }
    evaluation = load_evaluation_set()

    reused = [case.text for case in evaluation.cases if case.text.casefold() in catalog]

    assert reused == []
    assert {case.language for case in evaluation.cases} == set(InterfaceLanguage)
