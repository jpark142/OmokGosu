"""Per-match read endpoint — powers the replay viewer.

Only the participants of a match (the recorded black or white user) may view
its moves. AI games count the lone human as a participant; nobody else can see
their AI-loss kibitzed.
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.db.models import Match, User
from omok_server.schemas import (
    ColorStr,
    GameOverReason,
    MatchDetail,
    Stone,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _color_of(match: Match, user_id: int) -> ColorStr | None:
    if match.black_user_id == user_id: return ColorStr.BLACK
    if match.white_user_id == user_id: return ColorStr.WHITE
    return None


def _winner_color(match: Match) -> ColorStr | None:
    if match.winner_user_id is None:
        return None
    if match.winner_user_id == match.black_user_id: return ColorStr.BLACK
    if match.winner_user_id == match.white_user_id: return ColorStr.WHITE
    return None


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(
    match_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MatchDetail:
    match = session.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="match not found")

    # Authorization: only the participants may view.
    if _color_of(match, user.id) is None:
        raise HTTPException(status_code=403, detail="not a participant of this match")

    # Look up opponent username(s).
    def _name(uid: int | None) -> str | None:
        if uid is None: return None
        u = session.get(User, uid)
        return u.username if u is not None else None

    # Deserialize moves.
    try:
        raw = json.loads(match.moves_json) if match.moves_json else []
    except json.JSONDecodeError:
        raw = []
    moves = [
        Stone(r=int(m["r"]), c=int(m["c"]), color=ColorStr(m["color"]))
        for m in raw
        if isinstance(m, dict) and "r" in m and "c" in m and "color" in m
    ]

    # Winner color: None if no human winner_user_id (e.g., AI win) — but we can
    # still infer for AI games by checking which color the AI was. For HVH/HVA,
    # if winner_user_id is set we map to color; otherwise (AI win in HVA) the
    # winning color is the one whose user_id is None.
    winner_color = _winner_color(match)
    if winner_color is None and match.is_ai_game:
        # AI won: figure out which slot was the AI (NULL user_id) and report
        # that color as the winner.
        if match.black_user_id is None and match.white_user_id is not None:
            winner_color = ColorStr.BLACK
        elif match.white_user_id is None and match.black_user_id is not None:
            winner_color = ColorStr.WHITE
        # else both NULL or both set — ambiguous, leave None

    return MatchDetail(
        match_id=match.id,
        game_id=match.game_id,
        black_username=_name(match.black_user_id) or ("AI" if match.is_ai_game and match.black_user_id is None else None),
        white_username=_name(match.white_user_id) or ("AI" if match.is_ai_game and match.white_user_id is None else None),
        winner_color=winner_color,
        over_reason=GameOverReason(match.over_reason),
        is_ai_game=match.is_ai_game,
        started_at=match.started_at.timestamp(),
        ended_at=match.ended_at.timestamp(),
        move_count=match.move_count,
        moves=moves,
    )
