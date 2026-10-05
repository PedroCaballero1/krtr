"""Tests that the step timer records exact per-step and total durations with a fake clock."""

import pytest

from krtr.back.ia.artifacts import TurnStep
from krtr.back.ia.timing import StepTimer


class FakeClock:
    """A clock that only moves when told to, in seconds."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_each_step_and_the_total_are_measured_in_milliseconds() -> None:
    """Untimed work between steps counts in the total, not in any step."""
    clock = FakeClock()
    timer = StepTimer(clock)
    with timer.measure(TurnStep.EMBEDDING):
        clock.now += 0.004
    clock.now += 0.010
    with timer.measure(TurnStep.MATCHING):
        clock.now += 0.001

    timings = timer.finish()

    assert timings.steps_ms == pytest.approx({TurnStep.EMBEDDING: 4.0, TurnStep.MATCHING: 1.0})
    assert timings.total_ms == pytest.approx(15.0)


def test_a_step_measured_twice_accumulates() -> None:
    """Two blocks of the same step add up instead of overwriting each other."""
    clock = FakeClock()
    timer = StepTimer(clock)
    for _ in range(2):
        with timer.measure(TurnStep.ACTION):
            clock.now += 0.002

    assert timer.finish().steps_ms[TurnStep.ACTION] == pytest.approx(4.0)


def test_a_step_that_raises_is_still_recorded() -> None:
    """A failing step's time is not lost, so a slow failure is visible."""
    clock = FakeClock()
    timer = StepTimer(clock)
    with pytest.raises(RuntimeError), timer.measure(TurnStep.ACTION):
        clock.now += 0.003
        raise RuntimeError("action failed")

    assert timer.finish().steps_ms[TurnStep.ACTION] == pytest.approx(3.0)
