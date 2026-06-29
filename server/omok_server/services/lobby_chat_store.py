"""Persistence for lobby (global) chat so history survives restarts/deploys.

Only the lobby channel is persisted — room/game chat stays ephemeral. Each
lobby message is mirrored to the `lobbychat` table; on first use the in-memory
buffer is hydrated from here. The table is bounded: every insert prunes
everything older than the newest `RETENTION` rows, so disk stays tiny and the
memory window stays fixed.
"""
from __future__ import annotations

from sqlalchemy import delete
from sqlmodel import Session, select

from omok_server.db.engine import engine
from omok_server.db.models import LobbyChat

# Rows kept on disk. ~500 messages × a few hundred bytes ≈ <200 KB.
RETENTION = 500
# How many recent messages to hydrate into the buffer / show on connect.
LOAD_LIMIT = 100


def load_recent(limit: int = LOAD_LIMIT) -> list[dict]:
    """Return up to `limit` most recent messages, oldest-first (display order),
    as plain dicts shaped like SChatMsg payloads."""
    with Session(engine) as db:
        rows = db.exec(
            select(LobbyChat).order_by(LobbyChat.id.desc()).limit(limit)
        ).all()
    rows.reverse()  # newest-first query → flip to oldest-first for the UI
    return [
        {
            "user_id": r.user_id,
            "username": r.username,
            "text": r.text,
            "server_time_ms": r.server_time_ms,
            "role": r.role,
            "is_system": r.is_system,
        }
        for r in rows
    ]


def persist(payload: dict) -> None:
    """Insert one lobby message, then prune to the newest RETENTION rows."""
    with Session(engine) as db:
        db.add(
            LobbyChat(
                user_id=int(payload.get("user_id", 0)),
                username=str(payload.get("username", ""))[:64],
                text=str(payload.get("text", ""))[:200],
                is_system=bool(payload.get("is_system", False)),
                role=str(payload.get("role", "player"))[:16],
                server_time_ms=int(payload.get("server_time_ms", 0)),
            )
        )
        db.commit()
        _prune(db)


def _prune(db: Session) -> None:
    """Drop all rows older than the newest RETENTION. No-op until the table
    exceeds RETENTION."""
    cutoff = db.exec(
        select(LobbyChat.id).order_by(LobbyChat.id.desc()).offset(RETENTION).limit(1)
    ).first()
    if cutoff is not None:
        db.exec(delete(LobbyChat).where(LobbyChat.id <= cutoff))
        db.commit()


def clear_all() -> None:
    """Test-only: wipe the persisted lobby history."""
    with Session(engine) as db:
        db.exec(delete(LobbyChat))
        db.commit()
