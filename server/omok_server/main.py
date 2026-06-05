"""FastAPI entrypoint for the OmokGosu server.

Dev:
    uvicorn omok_server.main:app --reload --port 8000
Prod (Docker / Fly.io):
    uvicorn omok_server.main:app --host 0.0.0.0 --port 8000 --workers 1
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omok_server import __version__
from omok_server.api import auth as auth_api
from omok_server.api import games as games_api
from omok_server.api import matches as matches_api
from omok_server.api import rooms as rooms_api
from omok_server.api import system as system_api
from omok_server.api import users as users_api
from omok_server.api import ws as ws_api
from omok_server.api import ws_lobby as ws_lobby_api
from omok_server.api import ws_rooms as ws_rooms_api
from omok_server.db.engine import init_db
from omok_server.game.room_manager import room_manager
from omok_server.middleware.version_gate import ClientVersionGateMiddleware
from omok_server.static import mount_spa


def _resolve_cors_origins() -> list[str]:
    """OMOK_CORS_ORIGINS="https://a.com,https://b.com" overrides defaults.

    In production (frontend served from the same origin) CORS is not needed
    at all, so this is mostly for unusual cross-origin deployments.
    """
    override = os.environ.get("OMOK_CORS_ORIGINS")
    if override:
        return [o.strip() for o in override.split(",") if o.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app() -> FastAPI:
    app = FastAPI(title="OmokGosu Server", version=__version__)

    # SQLite tables (User, Match). Idempotent on subsequent boots.
    init_db()

    # Install the broadcast hooks now that the WS modules are imported. This
    # keeps `game/room_manager.py` free of FastAPI imports.
    room_manager.broadcast_lobby = ws_lobby_api.broadcast_lobby
    room_manager.broadcast_room = ws_rooms_api.broadcast_room

    # Refuse /api/* from clients below MIN_CLIENT_VERSION (returns 426).
    # /api/version itself is exempt so old clients can still learn the gate.
    app.add_middleware(ClientVersionGateMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_api.router)
    app.include_router(auth_api.router)
    app.include_router(games_api.router)
    app.include_router(matches_api.router)
    app.include_router(rooms_api.router)
    app.include_router(users_api.router)
    app.include_router(ws_api.router)
    app.include_router(ws_lobby_api.router)
    app.include_router(ws_rooms_api.router)

    # SPA fallback MUST be registered LAST so /api/* and /ws/* match first.
    mount_spa(app)

    return app


app = create_app()
