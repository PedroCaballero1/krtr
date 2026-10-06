"""Tests the evaluation run on the shipped set with the offline model, and writing its proposals."""

from pathlib import Path

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.matching.evaluation.runner import apply_proposed_thresholds, run_evaluation
from krtr.back.ia.matching.models import EmbeddingModel
from krtr.back.ia.matching.thresholds import THRESHOLDS_FILE, load_thresholds
from krtr.back.security.oidc.artifacts import InterfaceLanguage

HASHING = IaModelsConfig(embedding=EmbeddingModel.HASHING)


def test_every_language_is_reported_and_the_proposal_makes_no_wrong_match() -> None:
    """The safety rule holds on the shipped set: no proposal answers the wrong question."""
    report = run_evaluation(HASHING)

    assert [item.language for item in report.languages] == list(InterfaceLanguage)
    assert all(item.proposed.matched_wrong == 0 for item in report.languages)
    assert all(item.proposed.repeat_false == 0 for item in report.languages)


def test_applying_writes_the_proposals_for_that_model(tmp_path: Path) -> None:
    """`--write` stores exactly the proposed thresholds, per language."""
    target = tmp_path / "thresholds.json"
    target.write_text(THRESHOLDS_FILE.read_text())
    report = run_evaluation(HASHING)

    apply_proposed_thresholds(report, target)

    written = load_thresholds(EmbeddingModel.HASHING, target)
    assert written == {item.language: item.proposed_thresholds for item in report.languages}
