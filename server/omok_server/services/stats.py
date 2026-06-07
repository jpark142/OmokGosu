"""Recording finished games + updating user stats.

Called by the WS handler after `GameSession` transitions to OVER. Performs
Match INSERT and per-user `wins/losses` UPDATE atomically within one SQLite
transaction.

Stats are denormalized into the User row (rather than aggregated on-read) so
listing N users in the lobby doesn't fan out to N COUNT queries. The atomic
`wins = wins + 1` SQL pattern keeps the counter race-free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlmodel import Session, select

from omok_server.db.engine import engine
from omok_server.db.models import Match, User
from omok_server.game.session import GameSession
from omok_server.schemas import (
    ColorStr,
    GameOverReason,
    GameStatus,
    PlayerKind,
    StatsUpdate,
)


def _serialize_moves(session: GameSession) -> str:
    """JSON-serialize the played moves in order. Each entry: {r, c, color}."""
    moves = []
    for stone in session.engine.stones():
        moves.append({"r": stone.r, "c": stone.c, "color": stone.color.value})
    return json.dumps(moves, separators=(",", ":"))


@dataclass(frozen=True)
class MatchResult:
    """Snapshot of what record_match wrote — used to build SGameOverMsg.stats_updates."""
    match_id: int | None
    stats_updates: list[StatsUpdate]


def _user_id_for(session: GameSession, color: ColorStr) -> int | None:
    info = session.players.get(color)
    if info is None:
        return None
    return info.user_id


def _winner_user_id(session: GameSession) -> int | None:
    if session.winner is None:
        return None
    return _user_id_for(session, session.winner)


def _both_user_ids(session: GameSession) -> tuple[int | None, int | None]:
    return _user_id_for(session, ColorStr.BLACK), _user_id_for(session, ColorStr.WHITE)


def _is_ai_game(session: GameSession) -> bool:
    return any(info.kind == PlayerKind.AI for info in session.players.values())


def record_match(session: GameSession, started_at: datetime) -> MatchResult:
    """Persist a finished GameSession.

    No-op if `session.status != OVER`. Returns a MatchResult listing the
    StatsUpdate entries that should be broadcast to the affected users so their
    clients can refresh without a separate REST round-trip.
    """
    if session.status != GameStatus.OVER or session.over_reason is None:
        return MatchResult(match_id=None, stats_updates=[])

    black_uid, white_uid = _both_user_ids(session)
    winner_uid = _winner_user_id(session)
    is_ai = _is_ai_game(session)
    ended_at = datetime.utcnow()

    match = Match(
        game_id=session.game_id,
        black_user_id=black_uid,
        white_user_id=white_uid,
        winner_user_id=winner_uid,
        over_reason=session.over_reason.value,
        started_at=started_at,
        ended_at=ended_at,
        move_count=session.engine.move_number,
        is_ai_game=is_ai,
        moves_json=_serialize_moves(session),
    )

    updates: list[StatsUpdate] = []
    with Session(engine) as db:
        db.add(match)
        # AI games are recorded for history (kept visible on the profile)
        # but deliberately do NOT touch wins/losses — those count only
        # ranked human-vs-human results. The Match row stays so the user
        # can still scroll through and replay AI games.
        if not is_ai:
            # For each human participant: if their color won → wins+1, else losses+1.
            # `session.winner` is the *color* that won, not a user_id, so we compare
            # to the player's color directly.
            for color in (ColorStr.BLACK, ColorStr.WHITE):
                uid = _user_id_for(session, color)
                if uid is None:
                    continue
                user = db.exec(select(User).where(User.id == uid)).first()
                if user is None:
                    continue
                if session.winner == color:
                    user.wins += 1
                elif session.winner is not None:
                    user.losses += 1
                # session.winner is None → draw (currently unreachable in Renju); skip.
                db.add(user)
                updates.append(StatsUpdate(user_id=user.id, wins=user.wins, losses=user.losses))
        db.commit()
        match_id = match.id

    return MatchResult(match_id=match_id, stats_updates=updates)


def fetch_user_stats(user_ids: Iterable[int]) -> dict[int, tuple[int, int]]:
    """Bulk-fetch wins/losses for the given user_ids. Used by GameSession.to_state_msg."""
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    with Session(engine) as db:
        rows = db.exec(select(User).where(User.id.in_(ids))).all()
    return {u.id: (u.wins, u.losses) for u in rows}
