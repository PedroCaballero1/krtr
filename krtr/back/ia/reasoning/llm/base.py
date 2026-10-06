"""Defines the contract of the LLM clients, how their use is measured, and the turn's budget.

Exists so the clarifier, the slot filler and the guard confirmer ask "something that returns a
schema-valid object" and never depend on a runtime. A client that can't answer in time raises
`LlmUnavailable`, and every caller then falls back to the deterministic path. Consumed by
`reasoning/llm/`.
"""

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)

MILLISECONDS_PER_SECOND = 1000

logger = logging.getLogger(__name__)


class LlmUnavailable(RuntimeError):
    """The LLM could not answer: a timeout, a runtime error, or output that doesn't validate."""


class LlmClient(ABC):
    """Asks a model for one object of a given schema, within the time it is given."""

    @abstractmethod
    def complete(self, prompt: str, schema: type[SchemaT], timeout_seconds: float) -> SchemaT:
        """Generates an answer constrained to the schema.

        Args:
            prompt: The full instruction, with the customer's text inside it.
            schema: The pydantic model the answer must validate against.
            timeout_seconds: How long this call may take, reading the prompt included.

        Returns:
            SchemaT: the validated answer.

        Raises:
            LlmUnavailable: if no valid answer arrives within `timeout_seconds`.
        """


class MeteredLlmClient:
    """Wraps a client, counts its calls and their time, and shares one time budget per turn.

    Exists so a turn's LLM calls (up to two guard confirmations, then the clarifier) fit the
    response-time SLA together (G16): each call gets only the LLM time left in the turn, and a
    call that can't fit isn't started. It also lets the engine report the LLM's share of each
    turn's latency and whether it ran at all (`TurnDetails.llm_used`). Consumed by `LlmTasks`;
    `reset()` is called by the engine at the start of every turn.
    """

    def __init__(
        self,
        client: LlmClient,
        turn_budget_seconds: float,
        min_call_seconds: float,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        """Wraps the client with a per-turn budget.

        Args:
            client: The client doing the work.
            turn_budget_seconds: The LLM time all calls of one turn may use together.
            min_call_seconds: The least time worth starting a call with; below it, the call is
                skipped, since reading the prompt alone would overrun the budget.
            clock: Returns the current time in seconds, for timing the calls.
        """
        self._client = client
        self._turn_budget_seconds = turn_budget_seconds
        self._min_call_seconds = min_call_seconds
        self._clock = clock
        self.calls = 0
        self.failures = 0  # Calls that raised `LlmUnavailable`, and calls skipped for time.
        self.elapsed_ms = 0.0

    def reset(self) -> None:
        """Starts a new turn: the counts go to zero and the whole budget is available again.

        Returns:
            None.
        """
        self.calls, self.failures, self.elapsed_ms = 0, 0, 0.0

    def remaining_seconds(self) -> float:
        """Tells how much LLM time the turn has left.

        Returns:
            float: the seconds left, never negative.
        """
        spent = self.elapsed_ms / MILLISECONDS_PER_SECOND
        return max(self._turn_budget_seconds - spent, 0.0)

    def complete(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Delegates the call with the time left in the turn, and records its duration.

        Args:
            prompt: The full instruction.
            schema: The answer's schema.

        Returns:
            SchemaT: the wrapped client's answer.

        Raises:
            LlmUnavailable: when the turn has too little time left, or the client raises it.
        """
        remaining = self.remaining_seconds()
        if remaining < self._min_call_seconds:
            self.failures += 1
            logger.info("Skipping an LLM call: %.2f s left in the turn", remaining)
            raise LlmUnavailable(f"Only {remaining:.2f} s of LLM time left in the turn")
        started_at = self._clock()
        self.calls += 1
        try:
            return self._client.complete(prompt, schema, remaining)
        except LlmUnavailable:
            self.failures += 1
            raise
        finally:
            self.elapsed_ms += (self._clock() - started_at) * MILLISECONDS_PER_SECOND
