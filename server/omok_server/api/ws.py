"""WebSocket endpoint: real-time game state + move submission + timer ticks.

Auth: WS connections must carry `?token=<jwt>`; failure → close(4401).
Game-over: the first emitter of SGameOverMsg also calls `services.stats.record_match`
within the session lock so the Match row + user stats are written exactly once.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sqlmodel import Session

from omok_server.auth.deps import get_current_user_ws, verify_ws_client_version
from omok_server.db.engine import engine
from omok_server.game.manager import manager
from omok_server.game.room_manager import room_manager
from omok_server.game.session import GameSession
from omok_server.schemas import (
    ClocksSnapshot,
    ColorStr,
    ForbiddenReason,
    GameOverReason,
    SErrorMsg,
    SForbiddenRejectedMsg,
    SGameOverMsg,
    SMoveAppliedMsg,
    SPongMsg,
    STimerTickMsg,
)
from omok_server.services.stats import record_match

router = APIRouter()

TIMER_TICK_INTERVAL_MS = 250


# Per-session WS bus.
@dataclass
class SessionBus:
    sockets: set[WebSocket] = field(default_factory=set)
    ticker_task: asyncio.Task | None = None


buses: dict[str, SessionBus] = {}


def _bus_for(game_id: str) -> SessionBus:
    bus = buses.get(game_id)
    if bus is None:
        bus = SessionBus()
        buses[game_id] = bus
    return bus


async def _send_json(ws: WebSocket, payload) -> None:
    try:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump()
        else:
            data = payload
        await ws.send_text(json.dumps(data, default=str))
    except Exception:
        pass


async def _broadcast(game_id: str, payload) -> None:
    bus = buses.get(game_id)
    if bus is None:
        return
    dead: list[WebSocket] = []
    for ws in list(bus.sockets):
        try:
            if hasattr(payload, "model_dump"):
                data = payload.model_dump()
            else:
                data = payload
            await ws.send_text(json.dumps(data, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        bus.sockets.discard(ws)


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _emit_game_over_msg(session: GameSession, fallback_reason: GameOverReason) -> SGameOverMsg:
    """Build the SGameOverMsg payload and run record_match exactly once.

    Caller must hold `session.lock`. Safe to call multiple times — only the
    first call persists and triggers room/lobby side-effects; subsequent calls
    just return the payload (empty stats_updates, no broadcasts).
    """
    reason = session.over_reason or fallback_reason
    stats_updates = []
    back_to_room: str | None = None
    if not session.recorded_match:
        result = record_match(session, session.started_at)
        session.recorded_match = True
        stats_updates = result.stats_updates
        # If this game was hosted by a Room, transition the room back to LOBBY
        # and push the new state to room + lobby subscribers. Lock order
        # discipline: this is called while holding session.lock, and we only
        # acquire room locks inside room_manager (game.lock → room.lock).
        room_id = room_manager.find_by_game(session.game_id)
        if room_id is not None:
            updated_room = await room_manager.handle_game_over(room_id)
            back_to_room = room_id
            if updated_room is not None:
                # Lazy imports to avoid module-load circularity with api/rooms.py.
                from omok_server.api.rooms import room_to_detail, room_to_summary

                with Session(engine) as db:
                    detail = room_to_detail(updated_room, db).model_dump()
                    summary = room_to_summary(updated_room, db).model_dump()
                await room_manager.broadcast_room(room_id, {"type": "room_state", "room": detail})
                await room_manager.broadcast_lobby({
                    "type": "lobby_update", "action": "updated",
                    "room_id": room_id, "room": summary,
                })
    return SGameOverMsg(
        winner=session.winner, reason=reason,
        stats_updates=stats_updates, back_to_room=back_to_room,
    )


async def _broadcast_move_and_state(session: GameSession, game_id: str) -> None:
    move = session.engine.last_move()
    if move is not None:
        await _broadcast(
            game_id,
            SMoveAppliedMsg(
                move=move,
                move_number=session.engine.move_number,
                last_move_at_ms=_now_ms(),
            ),
        )
    await _broadcast(game_id, session.to_state_msg())
    if session.is_over():
        await _broadcast(game_id, await _emit_game_over_msg(session, GameOverReason.FIVE))


async def _play_ai_turns(session: GameSession, game_id: str) -> None:
    """While the side-to-move is an AI player, have it play one move at a time.
    Caller must hold `session.lock`."""
    while not session.is_over():
        color = session.engine.side_to_move
        ai = session.get_ai_for(color)
        if ai is None:
            return
        await asyncio.sleep(0.4)
        r, c = ai.choose_move(session.engine, color, budget_ms=800)
        reason = session.apply_move(r, c, color)
        if reason is not None:
            await _broadcast(
                game_id,
                SErrorMsg(message=f"AI produced invalid move ({r},{c}): {reason.value}"),
            )
            return
        await _broadcast_move_and_state(session, game_id)


async def _start_ticker_if_needed(session: GameSession) -> None:
    bus = _bus_for(session.game_id)
    if bus.ticker_task is not None and not bus.ticker_task.done():
        return

    async def tick_loop():
        try:
            while True:
                await asyncio.sleep(TIMER_TICK_INTERVAL_MS / 1000)
                async with session.lock:
                    timed_out = session.check_timeout()
                    if session.is_over():
                        if timed_out is not None:
                            await _broadcast(
                                session.game_id,
                                await _emit_game_over_msg(session, GameOverReason.TIMEOUT),
                            )
                        await _broadcast(session.game_id, session.to_state_msg())
                        return
                    snap = STimerTickMsg(
                        clocks=ClocksSnapshot(
                            black=session.clock.live_snapshot_for(ColorStr.BLACK),
                            white=session.clock.live_snapshot_for(ColorStr.WHITE),
                        ),
                        to_move=session.engine.side_to_move,
                        server_time_ms=_now_ms(),
                    )
                await _broadcast(session.game_id, snap)
        except asyncio.CancelledError:
            pass

    bus.ticker_task = asyncio.create_task(tick_loop())


@router.websocket("/ws/games/{game_id}")
async def game_ws(ws: WebSocket, game_id: str):
    if not await verify_ws_client_version(ws):
        return
    # Token validation second — closes the socket on failure.
    user = await get_current_user_ws(ws)
    if user is None:
        return

    session = manager.get(game_id)
    if session is None:
        await ws.close(code=4404)
        return

    # Authorization: this user must be a participant. AI games allow only the
    # one human participant. HVH games allow either user_id assigned to the session.
    participant_ids = {info.user_id for info in session.players.values() if info.user_id is not None}
    if participant_ids and user.id not in participant_ids:
        await ws.close(code=4403)
        return

    await ws.accept()
    bus = _bus_for(game_id)
    bus.sockets.add(ws)
    await _send_json(ws, session.to_state_msg())
    await _start_ticker_if_needed(session)

    # If side-to-move is an AI (e.g. reconnect during an AI think), play now.
    async with session.lock:
        if not session.is_over():
            await _play_ai_turns(session, game_id)

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
            if mtype == "resign":
                color_str = msg.get("color")
                try:
                    color = ColorStr(color_str) if color_str else session.engine.side_to_move
                except ValueError:
                    color = session.engine.side_to_move
                async with session.lock:
                    session.resign(color)
                    over_msg = await _emit_game_over_msg(session, GameOverReason.RESIGN)
                await _broadcast(game_id, over_msg)
                await _broadcast(game_id, session.to_state_msg())
                continue
            if mtype == "move":
                r = msg.get("r")
                c = msg.get("c")
                if not isinstance(r, int) or not isinstance(c, int):
                    await _send_json(ws, SErrorMsg(message="move requires int r,c"))
                    continue
                async with session.lock:
                    color_to_play = session.engine.side_to_move
                    # Authorization: the WS user must own the color about to play
                    # (or be the human in an HVA game). If user_id is set on the
                    # side-to-move slot, only that user may move.
                    info = session.players.get(color_to_play)
                    if info is not None and info.user_id is not None and info.user_id != user.id:
                        await _send_json(
                            ws,
                            SForbiddenRejectedMsg(r=r, c=c, reason=ForbiddenReason.NOT_YOUR_TURN),
                        )
                        continue
                    reason = session.apply_move(r, c, color_to_play)
                    if reason is not None:
                        await _send_json(ws, SForbiddenRejectedMsg(r=r, c=c, reason=reason))
                        continue
                    await _broadcast_move_and_state(session, game_id)
                    await _play_ai_turns(session, game_id)
                continue

            await _send_json(ws, SErrorMsg(message=f"unknown type: {mtype}"))
    except WebSocketDisconnect:
        pass
    finally:
        bus.sockets.discard(ws)
        if not bus.sockets and bus.ticker_task is not None:
            bus.ticker_task.cancel()
            bus.ticker_task = None
