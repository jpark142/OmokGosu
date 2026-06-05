"""WebSocket endpoint for a single room.

Each connected member receives room_state pushes when guests join/ready/leave
and a room_game_started message when the host clicks Start. Start is a 2-step
operation: validate room state (room_manager) → create GameSession (manager) →
broadcast game_id so both clients navigate to /games/{id}.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.api.rooms import leave_one_room, room_to_detail, room_to_summary
from omok_server.db.engine import engine
from omok_server.db.models import User
from omok_server.game.manager import manager as game_manager
from omok_server.game.room_manager import room_manager
from omok_server.game.session import GameSession
from omok_server.schemas import GameMode, SErrorMsg, SPongMsg

router = APIRouter()


@dataclass
class RoomBus:
    sockets: set[WebSocket] = field(default_factory=set)


_buses: dict[str, RoomBus] = {}


def _bus_for(room_id: str) -> RoomBus:
    bus = _buses.get(room_id)
    if bus is None:
        bus = RoomBus()
        _buses[room_id] = bus
    return bus


async def _send_json(ws: WebSocket, payload) -> None:
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload
        await ws.send_text(json.dumps(data, default=str))
    except Exception:
        pass


async def broadcast_room(room_id: str, payload: dict) -> None:
    bus = _buses.get(room_id)
    if bus is None:
        return
    dead: list[WebSocket] = []
    for ws in list(bus.sockets):
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        bus.sockets.discard(ws)


async def _send_room_state(room_id: str, target_ws: WebSocket | None = None) -> None:
    room = room_manager.get(room_id)
    if room is None:
        return
    with Session(engine) as db:
        payload = {"type": "room_state", "room": room_to_detail(room, db).model_dump()}
    if target_ws is not None:
        await _send_json(target_ws, payload)
    else:
        await broadcast_room(room_id, payload)


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(ws: WebSocket, room_id: str):
    if not await verify_ws_client_version(ws):
        return
    user = await get_current_user_ws(ws)
    if user is None:
        return

    room = room_manager.get(room_id)
    if room is None:
        await ws.close(code=4404)
        return
    if not room.is_member(user.id):
        await ws.close(code=4403)
        return

    await ws.accept()
    bus = _bus_for(room_id)
    bus.sockets.add(ws)
    await _send_room_state(room_id, target_ws=ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(ws, SErrorMsg(message="invalid JSON"))
                continue

            mtype = msg.get("type")

            if mtype == "ping":
                await _send_json(ws, SPongMsg())
                continue

            if mtype == "ready":
                value = bool(msg.get("value", False))
                updated = await room_manager.set_ready(room_id, user_id=user.id, value=value)
                if updated is None:
                    await _send_json(ws, SErrorMsg(message="cannot set ready"))
                    continue
                await _send_room_state(room_id)
                with Session(engine) as db:
                    await room_manager.broadcast_lobby({
                        "type": "lobby_update",
                        "action": "updated",
                        "room_id": room_id,
                        "room": room_to_summary(updated, db).model_dump(),
                    })
                continue

            if mtype == "start":
                room_now = room_manager.get(room_id)
                if room_now is None or room_now.host_user_id != user.id:
                    await _send_json(ws, SErrorMsg(message="only host can start"))
                    continue
                if not room_now.can_start():
                    await _send_json(ws, SErrorMsg(message="guest not ready"))
                    continue
                # Resolve usernames once for the GameSession players dict.
                with Session(engine) as db:
                    host_user = db.get(User, room_now.host_user_id)
                    guest_user = db.get(User, room_now.guest_user_id) if room_now.guest_user_id else None
                if host_user is None or guest_user is None:
                    await _send_json(ws, SErrorMsg(message="member missing"))
                    continue
                session = GameSession.new(
                    mode=GameMode.HVH,
                    human_name=host_user.username,
                    human_user_id=host_user.id,
                    guest_name=guest_user.username,
                    guest_user_id=guest_user.id,
                )
                await game_manager.add(session)
                started = await room_manager.start_game(
                    room_id, host_user_id=user.id, game_id=session.game_id
                )
                if started is None:
                    # Race condition: room mutated between our check and start.
                    await _send_json(ws, SErrorMsg(message="failed to start"))
                    continue
                await broadcast_room(room_id, {"type": "room_game_started", "game_id": session.game_id})
                await _send_room_state(room_id)
                with Session(engine) as db:
                    await room_manager.broadcast_lobby({
                        "type": "lobby_update",
                        "action": "updated",
                        "room_id": room_id,
                        "room": room_to_summary(started, db).model_dump(),
                    })
                continue

            if mtype == "leave":
                with Session(engine) as db:
                    await leave_one_room(room_id, user_id=user.id, db=db)
                await ws.close()
                return

            await _send_json(ws, SErrorMsg(message=f"unknown type: {mtype}"))
    except WebSocketDisconnect:
        pass
    finally:
        bus.sockets.discard(ws)
