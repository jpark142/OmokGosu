"""WebSocket endpoint: real-time game state + move submission + timer ticks.

One WS connection per browser tab. A `GameSession` can have multiple WS
connections (multi-tab spectating / two-tab HVH). Broadcasts are per-session.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Iterable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from omok_server.game.manager import manager
from omok_server.game.session import GameSession
from omok_server.schemas import (
    ClocksSnapshot,
    ColorStr,
    GameOverReason,
    PlayerKind,
    SErrorMsg,
    SForbiddenRejectedMsg,
    SGameOverMsg,
    SMoveAppliedMsg,
    SPongMsg,
    SStateMsg,
    STimerTickMsg,
)

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
    """Send a Pydantic model (or dict) as JSON, ignoring closed connections."""
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
        await _broadcast(
            game_id,
            SGameOverMsg(
                winner=session.winner,
                reason=session.over_reason or GameOverReason.FIVE,
            ),
        )


async def _play_ai_turns(session: GameSession, game_id: str) -> None:
    """While the side-to-move is an AI player, have it play one move at a time.

    Caller must hold `session.lock`.
    """
    while not session.is_over():
        color = session.engine.side_to_move
        ai = session.get_ai_for(color)
        if ai is None:
            return
        # Small UX delay so the human sees their own move before the AI's appears,
        # and the AI's clock visibly consumes some time.
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
                                SGameOverMsg(
                                    winner=session.winner,
                                    reason=GameOverReason.TIMEOUT,
                                ),
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
    session = manager.get(game_id)
    if session is None:
        await ws.close(code=4404)
        return

    await ws.accept()
    bus = _bus_for(game_id)
    bus.sockets.add(ws)
    # Send initial state snapshot.
    await _send_json(ws, session.to_state_msg())
    await _start_ticker_if_needed(session)

    # If the side-to-move is an AI (e.g. BLACK is AI at game start, or we reconnected
    # during an AI's think), play it now. No-op when the human is to move.
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
                # The resigning player is whoever's turn it is from this socket's view.
                # In HVH on two tabs we accept resignation from either side: client passes color.
                color_str = msg.get("color")
                try:
                    color = ColorStr(color_str) if color_str else session.engine.side_to_move
                except ValueError:
                    color = session.engine.side_to_move
                async with session.lock:
                    session.resign(color)
                await _broadcast(
                    game_id,
                    SGameOverMsg(winner=session.winner, reason=GameOverReason.RESIGN),
                )
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
                    reason = session.apply_move(r, c, color_to_play)
                    if reason is not None:
                        await _send_json(
                            ws,
                            SForbiddenRejectedMsg(r=r, c=c, reason=reason),
                        )
                        continue
                    await _broadcast_move_and_state(session, game_id)
                    # If the next side is an AI, play its move(s) before unlocking.
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
