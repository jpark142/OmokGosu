"""SPA fallback (static.py) — only runs if `web/dist` exists.

These tests verify the FastAPI mount serves index.html for unknown routes
and that the Cache-Control header is set so deployed bundles aren't stuck
in old tabs across a redeploy.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _dist() -> Path:
    # server/tests/test_static.py → repo root → web/dist
    return Path(__file__).resolve().parents[2] / "web" / "dist"


pytestmark = pytest.mark.skipif(
    not (_dist() / "index.html").exists(),
    reason="web/dist missing — run `npm run build` first to enable SPA tests",
)


def test_root_serves_index(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert r.headers.get("cache-control") == "no-store"


def test_spa_fallback_for_unknown_route(client) -> None:
    # /lobby is a frontend route; the server has no handler for it. SPA
    # fallback should return index.html so React Router can take over.
    r = client.get("/lobby")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert r.headers.get("cache-control") == "no-store"


def test_api_routes_not_shadowed_by_spa(client) -> None:
    # The SPA fallback is registered last; /api/version must still hit the
    # actual handler instead of being treated as a SPA route.
    r = client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body and "min_client_version" in body


def test_assets_are_served_with_their_own_content_type(client) -> None:
    # Find some asset that vite produced (the file name is hashed).
    assets_dir = _dist() / "assets"
    if not assets_dir.is_dir():
        pytest.skip("no assets/ folder")
    js_files = list(assets_dir.glob("*.js"))
    if not js_files:
        pytest.skip("no JS bundle to check")
    name = js_files[0].name
    r = client.get(f"/assets/{name}")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "javascript" in ct
