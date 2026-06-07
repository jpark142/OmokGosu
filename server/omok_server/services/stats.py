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
    is_aborted = session.over_reason == GameOverReason.ABORTED
    with Session(engine) as db:
        db.add(match)
        # AI games are recorded for history (kept visible on the profile)
        # but deliberately do NOT touch wins/losses — those count only
        # ranked human-vs-human results. The Match row stays so the user
        # can still scroll through and replay AI games. Aborted games (resign
        # before move 1) are kept on the history with reason=ABORTED but also
        # leave wins/losses/draws untouched.
        if not is_ai and not is_aborted:
            # For each human participant: if their color won → wins+1, lost
            # color → losses+1, draw → draws+1. `session.winner` is the *color*
            # that won (not a user_id), so we compare to the player's color
            # directly. Draws are tracked separately from wins/losses so the
            # UI can show 승/무/패 without polluting the win-rate denominator.
            is_draw = session.over_reason == GameOverReason.DRAW
            for color in (ColorStr.BLACK, ColorStr.WHITE):
                uid = _user_id_for(session, color)
                if uid is None:
                    continue
                user = db.exec(select(User).where(User.id == uid)).first()
                if user is None:
                    continue
                if is_draw:
                    user.draws += 1
                elif session.winner == color:
                    user.wins += 1
                else:
                    user.losses += 1
                db.add(user)
                updates.append(StatsUpdate(
                    user_id=user.id, wins=user.wins, losses=user.losses, draws=user.draws,
                ))
        db.commit()
        match_id = match.id

    return MatchResult(match_id=match_id, stats_updates=updates)


def fetch_user_stats(user_ids: Iterable[int]) -> dict[int, tuple[int, int, int]]:
    """Bulk-fetch (wins, losses, draws) for the given user_ids.

    Used by GameSession.to_state_msg to hydrate the in-game player cards.
    """
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    with Session(engine) as db:
        rows = db.exec(select(User).where(User.id.in_(ids))).all()
    return {u.id: (u.wins, u.losses, u.draws) for u in rows}


def fetch_user_ranks(user_ids: Iterable[int]) -> dict[int, int]:
    """For each user_id that has at least one decided game (wins + losses > 0),
    return their global rank using the same ordering as `/api/users/leaderboard`
    (wins DESC, losses ASC, id ASC). Users with no decided games are omitted.

    The in-game participants panel hydrates rank from this.
    """
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    with Session(engine) as db:
        all_ranked = db.exec(
            select(User.id)
            .where((User.wins + User.losses) > 0)
            .order_by(User.wins.desc(), User.losses.asc(), User.id.asc())
        ).all()
    rank_by_id = {uid: i + 1 for i, uid in enumerate(all_ranked)}
    return {uid: rank_by_id[uid] for uid in ids if uid in rank_by_id}
