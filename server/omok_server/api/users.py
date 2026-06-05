"""User-scoped read endpoints: stats hover card backing data."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.db.models import Match, User
from omok_server.schemas import (
    ColorStr,
    GameOverReason,
    MatchSummary,
    RecentMatches,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/{user_id}/recent-matches", response_model=RecentMatches)
def recent_matches(
    user_id: int,
    _viewer: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = Query(default=5, ge=1, le=50),
) -> RecentMatches:
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")

    rows = session.exec(
        select(Match)
        .where((Match.black_user_id == user_id) | (Match.white_user_id == user_id))
        .order_by(Match.ended_at.desc())
        .limit(limit)
    ).all()

    out: list[MatchSummary] = []
    for m in rows:
        is_black = m.black_user_id == user_id
        your_color = ColorStr.BLACK if is_black else ColorStr.WHITE
        opponent_id = m.white_user_id if is_black else m.black_user_id
        opponent_name: str | None
        if opponent_id is None:
            opponent_name = None  # AI side
        else:
            opp = session.get(User, opponent_id)
            opponent_name = opp.username if opp is not None else None
        out.append(
            MatchSummary(
                match_id=m.id,
                opponent_username=opponent_name,
                opponent_user_id=opponent_id,
                your_color=your_color,
                you_won=(m.winner_user_id == user_id),
                over_reason=GameOverReason(m.over_reason),
                is_ai_game=m.is_ai_game,
                ended_at=m.ended_at.timestamp(),
                move_count=m.move_count,
            )
        )

    return RecentMatches(user_id=user_id, matches=out)
