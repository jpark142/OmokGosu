"""FastAPI entrypoint for the OmokGosu server.

Run locally:
    uvicorn omok_server.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omok_server.api import auth as auth_api
from omok_server.api import games as games_api
from omok_server.api import rooms as rooms_api
from omok_server.api import ws as ws_api
from omok_server.api import ws_lobby as ws_lobby_api
from omok_server.api import ws_rooms as ws_rooms_api
from omok_server.db.engine import init_db
from omok_server.game.room_manager import room_manager


def create_app() -> FastAPI:
    app = FastAPI(title="OmokGosu Server", version="0.3.0")

    # SQLite tables (User, Match). Idempotent on subsequent boots.
    init_db()

    # Install the broadcast hooks now that the WS modules are imported. This
    # keeps `game/room_manager.py` free of FastAPI imports.
    room_manager.broadcast_lobby = ws_lobby_api.broadcast_lobby
    room_manager.broadcast_room = ws_rooms_api.broadcast_room

    # Vite dev server runs on :5173. Allow it during local development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_api.router)
    app.include_router(games_api.router)
    app.include_router(rooms_api.router)
    app.include_router(ws_api.router)
    app.include_router(ws_lobby_api.router)
    app.include_router(ws_rooms_api.router)
    return app


app = create_app()
