"""Tests the `krtr back web serve` command's argument wiring."""

from typing import Any

import pytest
from typer.testing import CliRunner

from krtr.cli.back.web import handler
from krtr.cli.main import app

runner = CliRunner()


@pytest.fixture
def recorded_uvicorn_run(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Replaces uvicorn.run so the command never actually starts a server."""
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(handler.uvicorn, "run", lambda *a, **k: calls.append((a, k)))
    return calls


def test_serve_defaults_to_the_app_factory_and_default_host_port(
    recorded_uvicorn_run: list[tuple[Any, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies uvicorn gets the served-app factory, so it runs it at startup, not on import."""
    monkeypatch.delenv("PORT", raising=False)

    result = runner.invoke(app, ["back", "web", "serve"])

    assert result.exit_code == 0, result.stdout
    args, kwargs = recorded_uvicorn_run[0]
    assert args == ("krtr.back.web.app:create_served_app",)
    assert kwargs["factory"] is True
    assert kwargs["host"] == handler.DEFAULT_HOST
    assert kwargs["port"] == handler.DEFAULT_PORT
    assert kwargs["reload"] is False
    assert kwargs["server_header"] is False


def test_serve_passes_through_host_port_and_reload(
    recorded_uvicorn_run: list[tuple[Any, ...]],
) -> None:
    """Verifies explicit --host/--port/--reload reach uvicorn.run unchanged."""
    result = runner.invoke(
        app,
        ["back", "web", "serve", "--host", "127.0.0.1", "--port", "9000", "--reload"],
    )

    assert result.exit_code == 0, result.stdout
    _, kwargs = recorded_uvicorn_run[0]
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9000
    assert kwargs["reload"] is True
