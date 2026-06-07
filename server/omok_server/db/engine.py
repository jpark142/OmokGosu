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

        user_cols = {row[1] for row in conn.execute(text("PRAGMA table_info('user')"))}
        if "token_version" not in user_cols:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        if "draws" not in user_cols:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN draws INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()

        # One-shot backfill: AI games no longer affect wins/losses, but old
        # rows still have them counted. Recompute User.wins/losses from
        # Match rows where is_ai_game=0. Gated by PRAGMA user_version so it
        # runs exactly once per database.
        current_version = conn.execute(text("PRAGMA user_version")).scalar()
        if (current_version or 0) < 1:
            conn.execute(text("""
                UPDATE user SET
                    wins = (
                        SELECT COUNT(*) FROM match
                        WHERE match.is_ai_game = 0
                          AND match.winner_user_id = user.id
                    ),
                    losses = (
                        SELECT COUNT(*) FROM match
                        WHERE match.is_ai_game = 0
                          AND (match.black_user_id = user.id OR match.white_user_id = user.id)
                          AND match.winner_user_id IS NOT NULL
                          AND match.winner_user_id != user.id
                    )
            """))
            conn.execute(text("PRAGMA user_version = 1"))
            conn.commit()

        # v2: backfill draws from Match rows. Skipped HVA (is_ai_game=1) for
        # the same reason wins/losses are HVH-only.
        if (current_version or 0) < 2:
            conn.execute(text("""
                UPDATE user SET draws = (
                    SELECT COUNT(*) FROM match
                    WHERE match.is_ai_game = 0
                      AND match.over_reason = 'DRAW'
                      AND (match.black_user_id = user.id OR match.white_user_id = user.id)
                )
            """))
            conn.execute(text("PRAGMA user_version = 2"))
            conn.commit()


def get_session() -> Session:
    """FastAPI dependency / context manager helper. Caller is responsible for
    closing — typically `with Session(engine) as s: ...` in services, or
    `Depends(session_dep)` in route handlers (see deps.py)."""
    return Session(engine)
