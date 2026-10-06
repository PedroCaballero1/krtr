"""Runs the evaluation of one embedding model, language by language.

Exists as the one entry point of `krtr back ia evaluate`: it builds the selected model, embeds
the catalog, scores the evaluation set, counts the outcomes with the current thresholds, and
proposes measured ones. Consumed by `krtr/cli/back/ia/handler.py`.
"""

import logging
from pathlib import Path

import numpy as np

from krtr.back.ia.config import IaModelsConfig
from krtr.back.ia.matching.catalog import ExemplarCatalog
from krtr.back.ia.matching.config import CatalogConfig
from krtr.back.ia.matching.evaluation.artifacts import (
    EvaluationReport,
    EvaluationSet,
    LanguageReport,
)
from krtr.back.ia.matching.evaluation.dataset import load_evaluation_set
from krtr.back.ia.matching.evaluation.scoring import score_language
from krtr.back.ia.matching.evaluation.sweep import count_outcomes, propose_thresholds
from krtr.back.ia.matching.factory import build_embedder
from krtr.back.ia.matching.thresholds import (
    THRESHOLDS_FILE,
    LanguageThresholds,
    load_thresholds,
    save_thresholds,
)
from krtr.back.security.oidc.artifacts import InterfaceLanguage

logger = logging.getLogger(__name__)

P95 = 95


def run_evaluation(
    models: IaModelsConfig, evaluation: EvaluationSet | None = None
) -> EvaluationReport:
    """Evaluates the selected embedding model on every language.

    Args:
        models: The selection; only the embedding model and its cache are used.
        evaluation: The labelled set; the shipped one when None.

    Returns:
        EvaluationReport: per language, the outcomes now and with the proposed thresholds.
    """
    dataset = evaluation or load_evaluation_set()
    embedder = build_embedder(models.embedding, models.model_cache)
    catalog = ExemplarCatalog.load(embedder, CatalogConfig())
    current = load_thresholds(models.embedding)
    reports = []
    for language in InterfaceLanguage:
        logger.info("Evaluating %s on %s", models.embedding, language.value)
        cases = [case for case in dataset.cases if case.language == language]
        pairs = [pair for pair in dataset.pairs if pair.language == language]
        scores = score_language(embedder, catalog, cases, pairs)
        proposed = propose_thresholds(scores, current[language])
        reports.append(
            LanguageReport(
                language=language,
                cases=len(cases),
                pairs=len(pairs),
                current=count_outcomes(scores, current[language]),
                proposed=count_outcomes(scores, proposed),
                proposed_thresholds=proposed,
                embed_ms_p50=float(np.percentile(scores.embed_ms, 50)) if cases else 0.0,
                embed_ms_p95=float(np.percentile(scores.embed_ms, P95)) if cases else 0.0,
            )
        )
    return EvaluationReport(model=models.embedding, languages=reports)


def apply_proposed_thresholds(report: EvaluationReport, path: Path = THRESHOLDS_FILE) -> None:
    """Writes the proposed thresholds of every language into the thresholds file.

    Args:
        report: The evaluation whose proposals to apply.
        path: The thresholds file; the shipped `thresholds.json` by default.

    Returns:
        None.
    """
    proposed: LanguageThresholds = {
        language_report.language: language_report.proposed_thresholds
        for language_report in report.languages
    }
    save_thresholds(report.model, proposed, path)
    logger.info("Wrote the proposed %s thresholds", report.model.value)
