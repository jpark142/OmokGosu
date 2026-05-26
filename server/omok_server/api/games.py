"""REST endpoints for game creation / lookup / resign / rematch."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from omok_server.game.manager import manager
from omok_server.game.session import GameSession
from omok_server.schemas import (
    ColorStr,
    CreateGameRequest,
    CreateGameResponse,
    GameMode,
    SStateMsg,
)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/games", response_model=CreateGameResponse)
async def create_game(req: CreateGameRequest) -> CreateGameResponse:
    ai_name: str | None = None
    if req.ai_level is not None:
        ai_name = req.ai_level.value
        # Difficulty only applies to search-based AIs (minimax for now).
        if req.ai_difficulty and req.ai_level.value == "minimax":
            ai_name = f"{ai_name}:{req.ai_difficulty.lower()}"
    session = GameSession.new(
        mode=req.mode,
        human_name=req.player_name or "Player",
        ai_name=ai_name,
    )
    await manager.add(session)
    return CreateGameResponse(
        game_id=session.game_id,
        your_color=session.your_color(),
        ws_url=f"/ws/games/{session.game_id}",
    )


@router.get("/games/{game_id}", response_model=SStateMsg)
async def get_game(game_id: str) -> SStateMsg:
    s = manager.get(game_id)
    if s is None:
        raise HTTPException(status_code=404, detail="game not found")
    return s.to_state_msg()


@router.post("/games/{game_id}/resign")
async def resign(game_id: str, color: ColorStr) -> dict[str, bool]:
    s = manager.get(game_id)
    if s is None:
        raise HTTPException(status_code=404, detail="game not found")
    async with s.lock:
        s.resign(color)
    return {"ok": True}


@router.post("/games/{game_id}/rematch", response_model=CreateGameResponse)
async def rematch(game_id: str) -> CreateGameResponse:
    old = manager.get(game_id)
    if old is None:
        raise HTTPException(status_code=404, detail="game not found")
    new_session = GameSession.new(
        mode=old.mode,
        human_name=next(
            (p.name for p in old.players.values() if p.kind.value == "human"),
            "Player",
        ),
    )
    await manager.add(new_session)
    return CreateGameResponse(
        game_id=new_session.game_id,
        your_color=new_session.your_color(),
        ws_url=f"/ws/games/{new_session.game_id}",
    )
