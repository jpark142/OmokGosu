"""Mount the built React SPA on FastAPI.

In production (Docker / Fly.io) the frontend is bundled into the same image
as the server and served at the same origin — no CORS, no separate vite
process. In dev we still rely on vite at :5173 with its proxy.

If `web/dist` doesn't exist the mount is skipped silently (just a warning),
so dev environments don't break.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

_log = logging.getLogger(__name__)


def _resolve_dist() -> Path | None:
    override = os.environ.get("OMOK_WEB_DIST")
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    # main.py is at server/omok_server/main.py → web/dist is at <repo>/web/dist
    here = Path(__file__).resolve()
    # this file (static.py) is at server/omok_server/static.py → ../../..
    candidate = here.parents[2] / "web" / "dist"
    return candidate if candidate.is_dir() else None


def mount_spa(app: FastAPI) -> None:
    dist = _resolve_dist()
    if dist is None:
        _log.warning(
            "web/dist not found — SPA fallback disabled (dev mode is fine; "
            "set OMOK_WEB_DIST or run vite build for production)."
        )
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_html = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str) -> Response:
        # /api/* and /ws/* are matched by their routers earlier; if we reach
        # here it's a SPA route, a root-level asset (favicon, robots), or 404.
        target = dist / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        # SPA index — never cache so the freshly deployed bundle hash is seen
        # by tabs that hold an open connection through a redeploy.
        return FileResponse(
            index_html,
            headers={"Cache-Control": "no-store"},
        )

    _log.info("SPA mounted from %s", dist)
