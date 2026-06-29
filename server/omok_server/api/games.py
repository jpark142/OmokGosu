"""REST endpoints for game creation / lookup / resign / rematch.

Phase 3A: `POST /api/games` requires auth and tags the human side with the
caller's user_id. HVH mode is still allowed for now (Phase 3B will move HVH
behind the room flow); HVA records the caller's stats on game end.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from omok_server.auth.deps import get_current_user
from omok_server.db.models import User
from omok_server.game.manager import manager
from omok_server.game.session import GameSession
from omok_server.schemas import (
    ColorStr,
    CreateGameRequest,
    CreateGameResponse,
    SStateMsg,
)


def _is_dev_mode() -> bool:
    return os.environ.get("OMOK_DEV_MODE", "").strip() == "1"

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/games", response_model=CreateGameResponse)
async def create_game(
    req: CreateGameRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> CreateGameResponse:
    """Create a game.

    - HVA: the caller plays one color, AI fills the other.
    - HVH: the caller plays BOTH colors from this endpoint (solo / two-tab self-play).
      Multi-user HVH goes through the room flow in Phase 3B; this path is kept
      for solo testing and as the temporary entry point until rooms ship.
    """
    from omok_server.schemas import GameMode

    if req.mode == GameMode.HVH:
        session = GameSession.new(
            mode=req.mode,
            human_name=req.player_name or user.username,
            human_user_id=user.id,
            guest_name=user.username,
            guest_user_id=user.id,
        )
    else:
        ai_name: str | None = None
        if req.ai_level is not None:
            ai_name = req.ai_level.value
            if req.ai_difficulty and req.ai_level.value in ("minimax", "heuristic"):
                ai_name = f"{ai_name}:{req.ai_difficulty.lower()}"
        session = GameSession.new(
            mode=req.mode,
            human_name=req.player_name or user.username,
            ai_name=ai_name,
            human_user_id=user.id,
        )
    await manager.add(session)
    return CreateGameResponse(
        game_id=session.game_id,
        your_color=session.your_color(),
        ws_url=f"/ws/games/{session.game_id}",
    )


@router.get("/games/{game_id}", response_model=SStateMsg)
async def get_game(
    game_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> SStateMsg:
    s = manager.get(game_id)
    if s is None:
        raise HTTPException(status_code=404, detail="game not found")
    state = s.to_state_msg()
    # Reveal black's forbidden-move (금수) markers only to the black player;
    # strip them for white and spectators so the hints don't leak.
    black = s.players.get(ColorStr.BLACK)
    is_black_player = black is not None and black.user_id is not None and black.user_id == user.id
    if not is_black_player and state.forbidden_squares:
        state = state.model_copy(update={"forbidden_squares": []})
    return state


@router.post("/games/{game_id}/resign")
async def resign(
    game_id: str,
    color: ColorStr,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    s = manager.get(game_id)
    if s is None:
        raise HTTPException(status_code=404, detail="game not found")
    async with s.lock:
        s.resign(color)
    return {"ok": True}


@router.post("/games/{game_id}/_dev/clip-clock")
async def dev_clip_clock(
    game_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """Dev-only: collapse both sides' main time down to 10 seconds so the
    byo-yomi flow can be exercised in seconds instead of 5 real minutes.
    Gated by the `OMOK_DEV_MODE` env var; returns 403 otherwise."""
    if not _is_dev_mode():
        raise HTTPException(status_code=403, detail="dev mode disabled")
    s = manager.get(game_id)
    if s is None:
        raise HTTPException(status_code=404, detail="game not found")
    async with s.lock:
        # Don't touch in_byoyomi / byoyomi_periods — those should still
        # transition naturally via _advance_state once the 10s runs out.
        s.clock.black.main_ms = min(s.clock.black.main_ms, 10_000)
        s.clock.white.main_ms = min(s.clock.white.main_ms, 10_000)
        # Rebase the active side's turn start so the remaining 10s is
        # counted from "now," not from whenever the turn really began.
        if s.clock.active is not None and s.clock.turn_started_at_ms is not None:
            s.clock.turn_started_at_ms = s.clock.now()
    return {"ok": True}


@router.post("/games/{game_id}/rematch", response_model=CreateGameResponse)
async def rematch(
    game_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> CreateGameResponse:
    old = manager.get(game_id)
    if old is None:
        raise HTTPException(status_code=404, detail="game not found")
    new_session = GameSession.new(
        mode=old.mode,
        human_name=user.username,
        human_user_id=user.id,
    )
    await manager.add(new_session)
    return CreateGameResponse(
        game_id=new_session.game_id,
        your_color=new_session.your_color(),
        ws_url=f"/ws/games/{new_session.game_id}",
    )
