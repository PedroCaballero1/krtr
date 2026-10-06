"""Times a turn, in total and per step, so every response carries its own latency (G16).

Exists so the slow step of a turn is visible, not only its total: the < 1 s target depends on
steps that will change (the real embedder, Neon reads, the LLM clarifier). Consumed by
`engine/engine.py`; the result travels in `AgentReply.timings`.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from krtr.back.ia.artifacts import TurnStep, TurnTimings

MILLISECONDS_PER_SECOND = 1000


class StepTimer:
    """Accumulates the duration of each step of one turn, from its creation to `finish`.

    Exists so the engine times steps with a `with` block instead of repeating clock arithmetic.
    The clock is injectable so tests can assert exact durations.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        """Starts the turn's clock.

        Args:
            clock: Returns the current time in seconds; `time.perf_counter` by default.
        """
        self._clock = clock
        self._started_at = clock()
        self._steps_ms: dict[TurnStep, float] = {}

    @contextmanager
    def measure(self, step: TurnStep) -> Iterator[None]:
        """Times the block it wraps and adds it to the step's duration.

        Args:
            step: The step the block belongs to.

        Returns:
            Iterator[None]: a context manager; the duration is recorded even if the block raises.
        """
        started_at = self._clock()
        try:
            yield
        finally:
            elapsed_ms = (self._clock() - started_at) * MILLISECONDS_PER_SECOND
            self._steps_ms[step] = self._steps_ms.get(step, 0.0) + elapsed_ms

    def finish(self) -> TurnTimings:
        """Stops the turn's clock.

        Returns:
            TurnTimings: the total and the duration of each step that ran, in milliseconds.
        """
        total_ms = (self._clock() - self._started_at) * MILLISECONDS_PER_SECOND
        return TurnTimings(total_ms=total_ms, steps_ms=dict(self._steps_ms))
