"""Defines the contract of the LLM clients and how their use is measured.

Exists so the clarifier, the slot filler and the guard confirmer ask "something that returns a
schema-valid object" and never depend on a runtime. A client that can't answer in time raises
`LlmUnavailable`, and every caller then falls back to the deterministic path. Consumed by
`reasoning/llm/`.
"""

import time
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)

MILLISECONDS_PER_SECOND = 1000


class LlmUnavailable(RuntimeError):
    """The LLM could not answer: a timeout, a runtime error, or output that doesn't validate."""


class LlmClient(ABC):
    """Asks a model for one object of a given schema."""

    @abstractmethod
    def complete(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Generates an answer constrained to the schema.

        Args:
            prompt: The full instruction, with the customer's text inside it.
            schema: The pydantic model the answer must validate against.

        Returns:
            SchemaT: the validated answer.

        Raises:
            LlmUnavailable: if no valid answer arrives within the time budget.
        """


class MeteredLlmClient(LlmClient):
    """Wraps a client and counts its calls and their time, per turn.

    Exists so the engine can report the LLM's share of each turn's latency (G16) and whether it
    ran at all (`TurnDetails.llm_used`), without any caller timing its own calls.
    """

    def __init__(self, client: LlmClient) -> None:
        """Wraps the client.

        Args:
            client: The client doing the work.
        """
        self._client = client
        self.calls = 0
        self.failures = 0  # Calls that raised `LlmUnavailable` (timeouts, invalid output).
        self.elapsed_ms = 0.0

    def reset(self) -> None:
        """Starts a new turn's count.

        Returns:
            None.
        """
        self.calls, self.failures, self.elapsed_ms = 0, 0, 0.0

    def complete(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Delegates the call and records its duration, whether it succeeds or not.

        Args:
            prompt: The full instruction.
            schema: The answer's schema.

        Returns:
            SchemaT: the wrapped client's answer.

        Raises:
            LlmUnavailable: when the wrapped client raises it.
        """
        started_at = time.perf_counter()
        self.calls += 1
        try:
            return self._client.complete(prompt, schema)
        except LlmUnavailable:
            self.failures += 1
            raise
        finally:
            self.elapsed_ms += (time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND
