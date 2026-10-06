"""Tests the metered client: per-turn counts, and one LLM time budget shared by a turn's calls."""

import pytest
from pydantic import BaseModel

from krtr.back.ia.reasoning.llm.base import LlmUnavailable
from krtr.back.ia.reasoning.llm.config import LlmConfig
from tests.back.ia.reasoning.llm.fakes import UNAVAILABLE, PerfCounterClock, ScriptedLlm, metered

BUDGET = LlmConfig(turn_budget_seconds=3.5, min_call_seconds=1.5)


class Answer(BaseModel):
    ok: bool


def test_calls_and_time_are_counted_even_when_the_call_fails() -> None:
    """A timeout still cost time; the turn's latency must show it."""
    clock = PerfCounterClock()
    client = metered(ScriptedLlm({"ok": True}, UNAVAILABLE, clock=clock, seconds_per_call=0.5))

    assert client.complete("p", Answer) == Answer(ok=True)
    with pytest.raises(LlmUnavailable):
        client.complete("p", Answer)

    assert (client.calls, client.failures, client.elapsed_ms) == (2, 1, 1000.0)


def test_each_call_gets_only_the_llm_time_left_in_the_turn() -> None:
    """Two calls share the budget: after 2 s, the second call may take only 1.5 s."""
    clock = PerfCounterClock()
    llm = ScriptedLlm({"ok": True}, {"ok": True}, clock=clock, seconds_per_call=2.0)
    client = metered(llm, BUDGET)

    client.complete("p", Answer)
    client.complete("p", Answer)

    assert llm.timeouts == [3.5, 1.5]


def test_a_call_that_cannot_fit_is_skipped_without_reaching_the_model() -> None:
    """With 1.3 s left, reading the prompt alone would overrun: the template answer is used."""
    clock = PerfCounterClock()
    llm = ScriptedLlm({"ok": True}, {"ok": True}, clock=clock, seconds_per_call=2.2)
    client = metered(llm, BUDGET)
    client.complete("p", Answer)

    with pytest.raises(LlmUnavailable, match="1.30 s"):
        client.complete("p", Answer)

    assert len(llm.prompts) == 1
    assert (client.calls, client.failures) == (1, 1)


def test_reset_starts_a_new_turn_with_the_whole_budget() -> None:
    """Counts and budget belong to one turn."""
    clock = PerfCounterClock()
    llm = ScriptedLlm({"ok": True}, {"ok": True}, clock=clock, seconds_per_call=3.0)
    client = metered(llm, BUDGET)
    client.complete("p", Answer)

    client.reset()
    client.complete("p", Answer)

    assert llm.timeouts == [3.5, 3.5]
    assert (client.calls, client.elapsed_ms) == (1, 3000.0)
