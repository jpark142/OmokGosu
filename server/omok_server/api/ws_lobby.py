"""WebSocket endpoint for the lobby: live room list updates.

Read-only from the client side — the lobby is push-only. Membership/joining
happens via the REST endpoints in `api/rooms.py`; this channel just streams
created/updated/removed events so the list stays fresh without polling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.api.rooms import room_to_summary
from omok_server.db.engine import engine
from omok_server.game.room_manager import room_manager
from omok_server.schemas import SPongMsg

router = APIRouter()


@dataclass
class LobbyBus:
    sockets: set[WebSocket] = field(default_factory=set)


_bus = LobbyBus()


async def broadcast_lobby(payload: dict) -> None:
    dead: list[WebSocket] = []
    for ws in list(_bus.sockets):
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _bus.sockets.discard(ws)


@router.websocket("/ws/lobby")
async def lobby_ws(ws: WebSocket):
    if not await verify_ws_client_version(ws):
        return
    user = await get_current_user_ws(ws)
    if user is None:
        return

    await ws.accept()
    _bus.sockets.add(ws)
    # Initial snapshot of the current room list.
    with Session(engine) as db:
        payload = {
            "type": "lobby_snapshot",
            "rooms": [room_to_summary(r, db).model_dump() for r in room_manager.list()],
        }
    try:
        await ws.send_text(json.dumps(payload, default=str))
        while True:
            raw = await ws.receive_text()
            # The lobby channel only supports keepalive pings from the client.
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await ws.send_text(SPongMsg().model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        _bus.sockets.discard(ws)
