"""User-scoped read endpoints: profile, leaderboard, recent matches.

Route order matters: `/leaderboard` must be registered BEFORE `/{user_id}`,
otherwise FastAPI would treat "leaderboard" as a user_id and never match the
literal path. Same goes for any future fixed paths under `/api/users`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.db.models import Match, User
from omok_server.schemas import (
    ColorStr,
    GameOverReason,
    Leaderboard,
    LeaderboardEntry,
    MatchSummary,
    RecentMatches,
    UserSummary,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/leaderboard", response_model=Leaderboard)
def leaderboard(
    _viewer: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = Query(default=20, ge=1, le=100),
) -> Leaderboard:
    """Top users by total wins. Users with zero games are excluded so the
    board doesn't fill up with brand-new accounts. Stats include AI-game
    wins/losses — same as displayed elsewhere in the UI."""
    rows = session.exec(
        select(User)
        .where((User.wins + User.losses) > 0)
        .order_by(User.wins.desc(), User.losses.asc(), User.id.asc())
        .limit(limit)
    ).all()
    entries = [
        LeaderboardEntry(
            rank=i + 1,
            user_id=u.id,
            username=u.username,
            wins=u.wins,
            losses=u.losses,
            draws=u.draws,
        )
        for i, u in enumerate(rows)
    ]
    return Leaderboard(entries=entries)


@router.get("/{user_id}", response_model=UserSummary)
def get_user(
    user_id: int,
    viewer: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserSummary:
    """Return a single user's stats. Public to any logged-in caller. The
    `current_room_id` field is only populated when the caller is asking
    about themselves (privacy: don't reveal another user's location).
    """
    from omok_server.game.room_manager import room_manager

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    current_room_id = (
        room_manager.find_room_for_user(target.id) if target.id == viewer.id else None
    )
    return UserSummary(
        id=target.id,
        username=target.username,
        wins=target.wins,
        losses=target.losses,
        draws=target.draws,
        current_room_id=current_room_id,
    )


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
        # Distinguish draw, aborted, and loss-to-AI: all three can have
        # winner_user_id=NULL, but only over_reason disambiguates.
        is_draw = m.over_reason == GameOverReason.DRAW.value
        is_aborted = m.over_reason == GameOverReason.ABORTED.value
        out.append(
            MatchSummary(
                match_id=m.id,
                opponent_username=opponent_name,
                opponent_user_id=opponent_id,
                your_color=your_color,
                you_won=(not is_draw and not is_aborted and m.winner_user_id == user_id),
                is_draw=is_draw,
                is_aborted=is_aborted,
                over_reason=GameOverReason(m.over_reason),
                is_ai_game=m.is_ai_game,
                ended_at=m.ended_at.timestamp(),
                move_count=m.move_count,
            )
        )

    return RecentMatches(user_id=user_id, matches=out)
