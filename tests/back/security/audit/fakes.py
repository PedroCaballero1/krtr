"""Fakes shared by the audit and served-app tests: an in-memory recorder and a Neon guard."""

from typing import Any, NoReturn

from krtr.back.security.audit.event_names import EventName


class InMemoryRecorder:
    """Stands in for EventRecorder, keeping the recorded events in memory."""

    def __init__(self) -> None:
        """Starts with no recorded events."""
        self.events: list[tuple[EventName, dict[str, Any]]] = []

    def record_event(self, event_name: EventName, properties: dict[str, Any]) -> None:
        """Keeps the event instead of encrypting it and writing it to Neon."""
        self.events.append((event_name, properties))


def refuse_to_open_neon() -> NoReturn:
    """Stands in for NeonClient where opening a connection would be a bug."""
    raise AssertionError("a Neon connection must not be opened")
