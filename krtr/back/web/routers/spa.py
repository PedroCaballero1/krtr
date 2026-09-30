"""Defines the SPA fallback route that serves the built React app.

Exists so client-side routes (`/`, `/app`, and any nested route the SPA's
router owns) all resolve to the same `index.html`, letting React Router take
over in the browser, per §3.3/4.1 of docs/guia-web-seguridad.md. Registered
last in `create_app` so it only catches requests no other router matched.
Consumed by `krtr/back/web/app.py`.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

spa_router = APIRouter()

# Path prefixes that belong to other routers (or don't exist yet but will,
# per §3.4): never served the SPA shell, so a typo'd API call 404s instead
# of silently returning an HTML page.
_NON_SPA_PREFIXES = ("api/", "auth/", "docs", "redoc", "openapi.json", "healthz")


@spa_router.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str, request: Request) -> FileResponse:
    """Serves the SPA's `index.html` for any GET route the SPA itself owns.

    Exists so a full page load or refresh on a client-side route (e.g.
    `/app/support`) still gets the app shell instead of a 404.

    Args:
        full_path: The requested path, without the leading slash.
        request: The current request, used to read the configured frontend
            dist directory from `request.app.state.config`.

    Returns:
        FileResponse: the built `index.html`.

    Raises:
        HTTPException: 404 if `full_path` belongs to another router's
            namespace, or if the frontend has not been built yet.
    """
    dist_dir: Path = request.app.state.config.frontend_dist_dir
    index_path = dist_dir / "index.html"
    if full_path.startswith(_NON_SPA_PREFIXES) or not index_path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(index_path)
