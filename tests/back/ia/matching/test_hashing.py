"""Tests that the hashing embedder ranks spelling overlap the way the matcher expects."""

import numpy as np

from krtr.back.ia.matching.hashing import HashingEmbedder

EMBEDDER = HashingEmbedder()


def test_rows_are_unit_length_and_blank_text_is_zero() -> None:
    """Dot products are cosine similarities; text with no letters matches nothing."""
    vectors = EMBEDDER.embed(["saldo de mi cuenta", "?!"])

    assert np.isclose(np.linalg.norm(vectors[0]), 1.0)
    assert not vectors[1].any()


def test_accents_and_case_do_not_change_the_vector() -> None:
    """ "Crédito" and "credito" are the same word to the matcher."""
    accented, plain = EMBEDDER.embed(["Tarjeta de Crédito", "tarjeta de credito"])

    assert np.allclose(accented, plain)


def test_overlapping_phrases_score_higher_than_unrelated_ones() -> None:
    """A rephrased balance request is closer to a balance phrase than a football question."""
    reference, rephrased, unrelated = EMBEDDER.embed(
        ["cual es el saldo de mi cuenta", "saldo de mi cuenta", "quien gano el partido"]
    )

    assert reference @ rephrased > reference @ unrelated
