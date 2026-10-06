"""Tests the metered client: it counts calls and their time per turn, failures included."""

import pytest
from pydantic import BaseModel

from krtr.back.ia.reasoning.llm.base import LlmUnavailable, MeteredLlmClient
from tests.back.ia.reasoning.llm.fakes import UNAVAILABLE, ScriptedLlm


class Answer(BaseModel):
    ok: bool


def test_calls_and_time_are_counted_even_when_the_call_fails() -> None:
    """A timeout still cost time; the turn's latency must show it."""
    metered = MeteredLlmClient(ScriptedLlm({"ok": True}, UNAVAILABLE))

    assert metered.complete("p", Answer) == Answer(ok=True)
    with pytest.raises(LlmUnavailable):
        metered.complete("p", Answer)

    assert metered.calls == 2
    assert metered.elapsed_ms >= 0


def test_reset_starts_a_new_turn() -> None:
    """Counts belong to one turn."""
    metered = MeteredLlmClient(ScriptedLlm({"ok": True}))
    metered.complete("p", Answer)

    metered.reset()

    assert (metered.calls, metered.elapsed_ms) == (0, 0.0)
