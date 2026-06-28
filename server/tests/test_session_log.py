"""Usage-analytics session logging: the SessionLog service + the WsRegistry
offline↔online transition hook that drives it."""
from __future__ import annotations

import asyncio
import uuid

from sqlmodel import Session, col, select

from omok_server.auth.security import hash_password
from omok_server.db.engine import engine
from omok_server.db.models import SessionLog, User
from omok_server.services import session_log
from omok_server.ws.registry import WsRegistry


def _mk_user() -> int:
    with Session(engine) as db:
        u = User(username="u" + uuid.uuid4().hex[:10], password_hash=hash_password("pw1234"))
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id


def _sessions(user_id: int) -> list[SessionLog]:
    with Session(engine) as db:
        return db.exec(
            select(SessionLog)
            .where(SessionLog.user_id == user_id)
            .order_by(col(SessionLog.connected_at).asc())
        ).all()


def test_connect_opens_session() -> None:
    uid = _mk_user()
    session_log.record_connect(uid)
    rows = _sessions(uid)
    assert len(rows) == 1
    assert rows[0].disconnected_at is None


def test_disconnect_closes_latest_open() -> None:
    uid = _mk_user()
    session_log.record_connect(uid)
    session_log.record_disconnect(uid)
    rows = _sessions(uid)
    assert len(rows) == 1
    assert rows[0].disconnected_at is not None
    assert rows[0].disconnected_at >= rows[0].connected_at


def test_disconnect_without_open_is_noop() -> None:
    uid = _mk_user()
    session_log.record_disconnect(uid)  # nothing open
    assert _sessions(uid) == []


def test_disconnect_closes_only_one_open_row() -> None:
    uid = _mk_user()
    session_log.record_connect(uid)
    session_log.record_connect(uid)  # two opens (defensive: shouldn't normally happen)
    session_log.record_disconnect(uid)
    rows = _sessions(uid)
    assert len(rows) == 2
    assert sum(1 for r in rows if r.disconnected_at is None) == 1


def test_close_orphans_sets_zero_length() -> None:
    uid = _mk_user()
    session_log.record_connect(uid)
    closed = session_log.close_orphans()
    assert closed >= 1
    row = _sessions(uid)[-1]
    # Orphans close at connected_at so they can't inflate duration/peak stats.
    assert row.disconnected_at == row.connected_at


def test_registry_fires_session_on_transition_only() -> None:
    """Opening a second tab must NOT start a new session; closing the first of
    two sockets must NOT end it. Only first-in / last-out transitions fire."""
    async def run() -> list[tuple[int, bool]]:
        reg = WsRegistry()
        events: list[tuple[int, bool]] = []

        async def listener(user_id: int, online: bool) -> None:
            events.append((user_id, online))

        reg.add_session_listener(listener)
        ws1, ws2 = object(), object()
        await reg.register(1, ws1)    # offline → online  → fire (1, True)
        await reg.register(1, ws2)    # 2nd tab           → no fire
        await reg.unregister(1, ws1)  # still has ws2     → no fire
        await reg.unregister(1, ws2)  # online → offline  → fire (1, False)
        # Flush the fire-and-forget listener tasks.
        for _ in range(5):
            await asyncio.sleep(0)
        return events

    assert asyncio.run(run()) == [(1, True), (1, False)]
