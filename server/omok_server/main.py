"""FastAPI entrypoint for the OmokGosu server.

Run locally:
    uvicorn omok_server.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omok_server.api import auth as auth_api
from omok_server.api import games as games_api
from omok_server.api import ws as ws_api
from omok_server.db.engine import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="OmokGosu Server", version="0.2.0")

    # SQLite tables (User, Match). Idempotent on subsequent boots.
    init_db()

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
    app.include_router(ws_api.router)
    return app


app = create_app()
