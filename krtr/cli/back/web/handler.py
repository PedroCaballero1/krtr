"""Defines the `krtr back web` CLI commands.

Exists to expose running the krtr-web FastAPI app as a single, thin CLI
command, so the uvicorn invocation (host, port, import path) lives in one
place instead of being repeated in Docker, docs and scripts. Consumed by
`krtr/cli/back/__init__.py`, which registers `web_app`.
"""

import logging
import os

import typer
import uvicorn

logger = logging.getLogger(__name__)

web_app = typer.Typer(
    name="web", help="Run the krtr-web FastAPI application.", no_args_is_help=True
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


@web_app.command(name="serve")
def serve(
    host: str = typer.Option(DEFAULT_HOST, help="Host interface to bind to."),
    port: int = typer.Option(
        None,
        help="Port to listen on. Defaults to the $PORT env var (Cloud Run sets it), "
        f"or {DEFAULT_PORT} if that isn't set either.",
    ),
    reload: bool = typer.Option(False, help="Enable uvicorn's auto-reload for local development."),
) -> None:
    """Runs the krtr-web FastAPI application with uvicorn.

    Exists so the app starts the same way in local development, Docker and
    Cloud Run.

    Args:
        host: Host interface to bind to.
        port: Port to listen on. Resolved from $PORT at call time when not given.
        reload: When True, restarts the server on source changes (local dev only).

    Returns:
        None.
    """
    resolved_port = port if port is not None else int(os.environ.get("PORT", DEFAULT_PORT))
    logger.info("Starting krtr-web on %s:%d (reload=%s)", host, resolved_port, reload)
    uvicorn.run("krtr.back.web.app:app", host=host, port=resolved_port, reload=reload)
