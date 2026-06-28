"""Persist online sessions for usage analytics (DAU / session length / peak).

The WsRegistry signals offline↔online transitions; we turn each into a row:
one open row on connect, closed on disconnect. Everything here is best-effort
— a row lost to a crash or a reconnect race only costs a little analytics
accuracy, so nothing raises into the WS path. There is no read/stats endpoint
yet; this module's job is purely to capture the data so a dashboard can be
built later.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session, col, select

from omok_server.db.engine import engine
from omok_server.db.models import SessionLog

_log = logging.getLogger(__name__)


def record_connect(user_id: int) -> None:
    """Open a session row for `user_id` (their first live socket appeared)."""
    try:
        with Session(engine) as db:
            db.add(SessionLog(user_id=user_id, connected_at=datetime.utcnow()))
            db.commit()
    except Exception:  # analytics must never break the WS path
        _log.warning(
            "session_log: failed to record connect for user %s", user_id, exc_info=True
        )


def record_disconnect(user_id: int) -> None:
    """Close the user's most recent open session (their last socket went away).

    No-op if there's no open row — e.g. a reconnect race dropped the connect, or
    the open row was already closed by a startup orphan sweep."""
    try:
        with Session(engine) as db:
            row = db.exec(
                select(SessionLog)
                .where(
                    SessionLog.user_id == user_id,
                    col(SessionLog.disconnected_at).is_(None),
                )
                .order_by(col(SessionLog.connected_at).desc())
            ).first()
            if row is None:
                return
            row.disconnected_at = datetime.utcnow()
            db.add(row)
            db.commit()
    except Exception:
        _log.warning(
            "session_log: failed to record disconnect for user %s",
            user_id,
            exc_info=True,
        )


def close_orphans() -> int:
    """Close sessions left open by a previous run and return how many.

    After a restart the server can't possibly still hold sockets from before,
    so any still-open row is an orphan. We set `disconnected_at = connected_at`
    (a zero-length session) rather than NULL or "now": an unknown-length orphan
    must not be allowed to inflate session-duration or concurrent-peak stats.
    The connect event still counts toward "user was active that day"."""
    try:
        with Session(engine) as db:
            rows = db.exec(
                select(SessionLog).where(col(SessionLog.disconnected_at).is_(None))
            ).all()
            for r in rows:
                r.disconnected_at = r.connected_at
                db.add(r)
            db.commit()
            return len(rows)
    except Exception:
        _log.warning("session_log: failed to close orphaned sessions", exc_info=True)
        return 0
