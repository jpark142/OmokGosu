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

from omok_server.api import chat as chat_helpers
from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.api.rooms import leave_one_room, room_to_detail, room_to_summary
from omok_server.db.engine import engine
from omok_server.db.models import User
from omok_server.game.manager import manager as game_manager
from omok_server.game.room_manager import room_manager
from omok_server.game.session import GameSession
from omok_server.schemas import GameMode, SErrorMsg, SPongMsg
from omok_server.ws.registry import registry as ws_registry

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
    await ws_registry.register(user.id, ws)
    await _send_room_state(room_id, target_ws=ws)
    # Recent chat history (room-scoped) — only when non-empty.
    history = chat_helpers.history_for(f"room:{room_id}")
    if history is not None:
        await ws.send_text(json.dumps(history.model_dump(), default=str))

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

            if mtype == "chat":
                result = await chat_helpers.handle_incoming_chat(
                    key=f"room:{room_id}",
                    user=user,
                    text=msg.get("text", ""),
                    broadcast=lambda p: broadcast_room(room_id, p),
                )
                if result == chat_helpers.ChatResult.RATE_LIMITED:
                    await _send_json(ws, SErrorMsg(message="잠시 후 다시 시도하세요."))
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
                # System message: only when toggling INTO ready (not when unreadying).
                if value:
                    await chat_helpers.emit_system_message(
                        key=f"room:{room_id}",
                        text=f"{user.username} 님이 준비 완료.",
                        broadcast=lambda p: broadcast_room(room_id, p),
                    )
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
                # Drop a system note into the room chat so the next time the
                # players return to the room (post-game) there's clear context.
                await chat_helpers.emit_system_message(
                    key=f"room:{room_id}",
                    text="게임 시작!",
                    broadcast=lambda p: broadcast_room(room_id, p),
                )
                continue

            if mtype == "leave":
                with Session(engine) as db:
                    await leave_one_room(room_id, user_id=user.id, db=db)
                await ws.close()
                return

            if mtype == "kick":
                room_now, kicked_uid = await room_manager.kick_guest(
                    room_id, host_user_id=user.id
                )
                if room_now is None or kicked_uid is None:
                    await _send_json(ws, SErrorMsg(message="강퇴할 수 없습니다"))
                    continue
                # 1) Push the updated room state (guest slot now empty) to all
                #    members — including the kicked user, so their UI updates
                #    momentarily before the modal appears.
                await _send_room_state(room_id)
                # 2) Broadcast a directed "kicked" event. Every socket on the
                #    bus receives it, but the client only reacts when the
                #    user_id matches its own — clean way to target one user
                #    without per-socket addressing.
                await broadcast_room(room_id, {"type": "kicked", "user_id": kicked_uid})
                # 3) Lobby update + system message (resolve username inside
                #    a single DB session).
                with Session(engine) as db:
                    await room_manager.broadcast_lobby({
                        "type": "lobby_update", "action": "updated",
                        "room_id": room_id, "room": room_to_summary(room_now, db).model_dump(),
                    })
                    kicked = db.get(User, kicked_uid)
                    kicked_name = kicked.username if kicked is not None else "(unknown)"
                await chat_helpers.emit_system_message(
                    key=f"room:{room_id}",
                    text=f"{kicked_name} 님이 방장에 의해 강퇴되었습니다.",
                    broadcast=lambda p: broadcast_room(room_id, p),
                )
                continue

            await _send_json(ws, SErrorMsg(message=f"unknown type: {mtype}"))
    except WebSocketDisconnect:
        pass
    finally:
        bus.sockets.discard(ws)
        await ws_registry.unregister(user.id, ws)
