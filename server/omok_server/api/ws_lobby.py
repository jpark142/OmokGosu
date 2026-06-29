"""WebSocket endpoint for the lobby: live room list updates + global chat."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from sqlmodel import select

from omok_server.api import chat as chat_helpers
from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.api.rooms import room_to_summary
from omok_server.db.engine import engine
from omok_server.db.models import User
from omok_server.game.room_manager import room_manager
from omok_server.schemas import OnlinePresenceUser, SPongMsg, SPresenceMsg
from omok_server.ws.registry import registry as ws_registry

router = APIRouter()

# Single source of truth for the lobby channel key — chat_helpers gates DB
# persistence + buffer sizing on this exact value.
_LOBBY_CHAT_KEY = chat_helpers.LOBBY_CHAT_KEY


@dataclass
class LobbyBus:
    sockets: set[WebSocket] = field(default_factory=set)


_bus = LobbyBus()


_BROADCAST_SEND_TIMEOUT_S = 1.0


async def broadcast_lobby(payload: dict) -> None:
    body = json.dumps(payload, default=str)
    sockets = list(_bus.sockets)
    if not sockets:
        return

    async def _send(ws: WebSocket) -> WebSocket | None:
        try:
            await asyncio.wait_for(ws.send_text(body), timeout=_BROADCAST_SEND_TIMEOUT_S)
            return None
        except Exception:
            return ws

    results = await asyncio.gather(*(_send(ws) for ws in sockets))
    for dead_ws in results:
        if dead_ws is not None:
            _bus.sockets.discard(dead_ws)


def _presence_snapshot() -> dict:
    """Build the SPresenceMsg payload from the current registry state."""
    ids = ws_registry.online_user_ids()
    if not ids:
        return SPresenceMsg(users=[]).model_dump()
    with Session(engine) as db:
        rows = db.exec(select(User).where(User.id.in_(ids))).all()
    users = [
        OnlinePresenceUser(
            user_id=u.id,
            username=u.username,
            wins=u.wins,
            losses=u.losses,
            draws=u.draws,
        )
        for u in rows
    ]
    # Sort by username so clients render a stable order. Server-side sort
    # avoids every client having to re-sort on each presence update.
    users.sort(key=lambda u: u.username.lower())
    return SPresenceMsg(users=users).model_dump()


async def _broadcast_presence() -> None:
    """Registry presence-listener entry point: pushes the latest snapshot
    to every lobby WS. Called whenever a user goes online/offline anywhere
    in the system, not just in the lobby."""
    if not _bus.sockets:
        return
    await broadcast_lobby(_presence_snapshot())


# Registered at module import time so the registry fires this on every
# online-set change, regardless of which channel the user came in on.
ws_registry.add_presence_listener(_broadcast_presence)


@router.websocket("/ws/lobby")
async def lobby_ws(ws: WebSocket):
    if not await verify_ws_client_version(ws):
        return
    user = await get_current_user_ws(ws)
    if user is None:
        return

    await ws.accept()
    _bus.sockets.add(ws)
    # Initial snapshot of the current room list. Send room list + chat
    # history (if any) BEFORE registering, so the order on the wire is
    # deterministic: snapshot → chat_history → presence. Registering
    # triggers the presence listener, which broadcasts to every socket on
    # the bus including this one, giving the viewer their first presence
    # frame (with themselves in it).
    with Session(engine) as db:
        payload = {
            "type": "lobby_snapshot",
            "rooms": [room_to_summary(r, db).model_dump() for r in room_manager.list()],
        }
    try:
        await ws.send_text(json.dumps(payload, default=str))
        history = chat_helpers.history_for(_LOBBY_CHAT_KEY)
        if history is not None:
            await ws.send_text(json.dumps(history.model_dump(), default=str))
        await ws_registry.register(user.id, ws)

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await ws.send_text(SPongMsg().model_dump_json())
                continue
            if mtype == "chat":
                result = await chat_helpers.handle_incoming_chat(
                    key=_LOBBY_CHAT_KEY,
                    user=user,
                    text=msg.get("text", ""),
                    broadcast=broadcast_lobby,
                )
                if result == chat_helpers.ChatResult.RATE_LIMITED:
                    await ws.send_text(json.dumps(
                        {"type": "error", "message": "잠시 후 다시 시도하세요."},
                        default=str,
                    ))
                elif result == chat_helpers.ChatResult.SPAM_MUTED:
                    await ws.send_text(json.dumps(
                        {"type": "error", "message": "도배 감지 — 3분간 채팅이 금지됩니다."},
                        default=str,
                    ))
                elif result == chat_helpers.ChatResult.MUTED:
                    remain = chat_helpers.mute_remaining_s(_LOBBY_CHAT_KEY, user.id)
                    await ws.send_text(json.dumps(
                        {"type": "error", "message": f"채팅 금지 중 — {int(remain)+1}초 후 다시 시도하세요."},
                        default=str,
                    ))
                continue
            # Other client messages are ignored on the lobby channel.
    except WebSocketDisconnect:
        pass
    finally:
        # Remove from the bus FIRST so the unregister-triggered presence
        # broadcast doesn't try to write to a socket we're about to close.
        _bus.sockets.discard(ws)
        await ws_registry.unregister(user.id, ws)
