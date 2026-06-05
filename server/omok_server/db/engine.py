"""SQLite engine + session factory.

The DB file lives at `server/data/omok.sqlite` and is created on first startup
(`init_db()` is called from `main.create_app`). We do NOT use alembic — instead
`SQLModel.metadata.create_all` covers the schema. Schema is small enough and
breaking changes during Phase 3 will be handled by manually deleting the file.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine


def _resolve_db_path() -> Path:
    """Default to `<server>/data/omok.sqlite`, override via OMOK_DB_PATH."""
    override = os.environ.get("OMOK_DB_PATH")
    if override:
        return Path(override)
    # server/omok_server/db/engine.py → server/data/omok.sqlite
    server_dir = Path(__file__).resolve().parents[2]
    return server_dir / "data" / "omok.sqlite"


_DB_PATH = _resolve_db_path()
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False so FastAPI's threadpool can share the connection.
# We rely on SQLite's default serialized transactions for safety.
engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create tables if missing. Idempotent.

    Also runs lightweight inline migrations for additive schema changes —
    SQLModel.metadata.create_all doesn't ALTER existing tables, so columns
    added in later releases need an explicit ADD COLUMN here.
    """
    # Import side-effect: register all SQLModel tables on the metadata.
    from omok_server.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _run_inline_migrations()


def _run_inline_migrations() -> None:
    """ADD COLUMN for fields introduced after the initial schema.

    Idempotent — each migration is gated by a `PRAGMA table_info` check so
    re-running is a no-op once the column exists.
    """
    with engine.connect() as conn:
        from sqlalchemy import text
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info('match')"))}
        if "moves_json" not in cols:
            conn.execute(text(
                "ALTER TABLE match ADD COLUMN moves_json TEXT NOT NULL DEFAULT '[]'"
            ))
            conn.commit()


def get_session() -> Session:
    """FastAPI dependency / context manager helper. Caller is responsible for
    closing — typically `with Session(engine) as s: ...` in services, or
    `Depends(session_dep)` in route handlers (see deps.py)."""
    return Session(engine)
