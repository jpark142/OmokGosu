"""WebSocket endpoint for the lobby: live room list updates + global chat."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from omok_server.api import chat as chat_helpers
from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.api.rooms import room_to_summary
from omok_server.db.engine import engine
from omok_server.game.room_manager import room_manager
from omok_server.schemas import SPongMsg
from omok_server.ws.registry import registry as ws_registry

router = APIRouter()

_LOBBY_CHAT_KEY = "lobby"


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
    await ws_registry.register(user.id, ws)
    # Initial snapshot of the current room list.
    with Session(engine) as db:
        payload = {
            "type": "lobby_snapshot",
            "rooms": [room_to_summary(r, db).model_dump() for r in room_manager.list()],
        }
    try:
        await ws.send_text(json.dumps(payload, default=str))
        # Send recent chat history only if any exists (existing tests don't
        # expect an empty payload here).
        history = chat_helpers.history_for(_LOBBY_CHAT_KEY)
        if history is not None:
            await ws.send_text(json.dumps(history.model_dump(), default=str))

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
                continue
            # Other client messages are ignored on the lobby channel.
    except WebSocketDisconnect:
        pass
    finally:
        _bus.sockets.discard(ws)
        await ws_registry.unregister(user.id, ws)
