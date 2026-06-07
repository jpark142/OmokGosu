"""Stats / Match recording on game end."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Session, select

from omok_server.db.engine import engine
from omok_server.db.models import Match, User
from omok_server.game.session import GameSession
from omok_server.schemas import ColorStr, GameMode, GameStatus
from omok_server.services.stats import record_match


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def _make_user(username: str) -> int:
    from omok_server.auth.security import hash_password
    with Session(engine) as db:
        u = User(username=username, password_hash=hash_password("pw1234"))
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id


def test_record_match_no_op_when_game_still_in_progress() -> None:
    s = GameSession.new(mode=GameMode.HVA, human_name="alice", ai_name="minimax", human_user_id=_make_user(_u()))
    result = record_match(s, started_at=datetime.utcnow())
    assert result.match_id is None
    assert result.stats_updates == []


def test_record_match_hva_does_not_change_stats() -> None:
    """AI games are recorded for history but do NOT update wins/losses."""
    uid = _make_user(_u())
    s = GameSession.new(
        mode=GameMode.HVA, human_name="alice", ai_name="minimax", human_user_id=uid
    )
    # Force terminal state: human wins.
    human_color = next(c for c, info in s.players.items() if info.user_id == uid)
    s.status = GameStatus.OVER
    s.winner = human_color
    from omok_server.schemas import GameOverReason
    s.over_reason = GameOverReason.FIVE

    result = record_match(s, started_at=datetime.utcnow())
    # Match row is created (so it shows up in history)...
    assert result.match_id is not None
    # ...but no stats_updates are emitted — AI games are unranked.
    assert result.stats_updates == []

    with Session(engine) as db:
        m = db.exec(select(Match).where(Match.id == result.match_id)).first()
        assert m is not None
        assert m.is_ai_game is True
        assert m.winner_user_id == uid
        assert m.over_reason == "FIVE"

        # Wins/losses are unchanged from the freshly-made user (0/0).
        refreshed = db.exec(select(User).where(User.id == uid)).first()
        assert refreshed.wins == 0 and refreshed.losses == 0


def test_record_match_hva_loss_does_not_change_stats() -> None:
    """Losing to the AI shouldn't add a loss either."""
    uid = _make_user(_u())
    s = GameSession.new(
        mode=GameMode.HVA, human_name="bob", ai_name="minimax", human_user_id=uid
    )
    ai_color = next(c for c, info in s.players.items() if info.user_id is None)
    s.status = GameStatus.OVER
    s.winner = ai_color
    from omok_server.schemas import GameOverReason
    s.over_reason = GameOverReason.FIVE

    result = record_match(s, started_at=datetime.utcnow())
    assert result.match_id is not None
    assert result.stats_updates == []

    with Session(engine) as db:
        refreshed = db.exec(select(User).where(User.id == uid)).first()
        assert refreshed.wins == 0 and refreshed.losses == 0


def test_record_match_hvh_both_users_updated() -> None:
    uid_a = _make_user(_u())
    uid_b = _make_user(_u())
    s = GameSession.new(
        mode=GameMode.HVH,
        human_name="alice",
        human_user_id=uid_a,
        guest_name="bob",
        guest_user_id=uid_b,
    )
    # Whoever ends up as BLACK wins.
    s.status = GameStatus.OVER
    s.winner = ColorStr.BLACK
    from omok_server.schemas import GameOverReason
    s.over_reason = GameOverReason.FIVE

    result = record_match(s, started_at=datetime.utcnow())
    assert result.match_id is not None
    assert len(result.stats_updates) == 2

    black_uid = s.players[ColorStr.BLACK].user_id
    white_uid = s.players[ColorStr.WHITE].user_id

    by_user = {u.user_id: u for u in result.stats_updates}
    assert by_user[black_uid].wins == 1 and by_user[black_uid].losses == 0
    assert by_user[white_uid].wins == 0 and by_user[white_uid].losses == 1


def test_record_match_idempotency_via_session_flag() -> None:
    """The ws.py path guards re-recording via session.recorded_match. record_match
    itself is not idempotent (calling twice will INSERT twice); that's fine — the
    contract is that callers set session.recorded_match=True after the first call.

    Uses an HVH match because HVA no longer updates wins/losses.
    """
    uid_a = _make_user(_u())
    uid_b = _make_user(_u())
    s = GameSession.new(
        mode=GameMode.HVH,
        human_name="alice",
        human_user_id=uid_a,
        guest_name="bob",
        guest_user_id=uid_b,
    )
    s.status = GameStatus.OVER
    s.winner = ColorStr.BLACK
    from omok_server.schemas import GameOverReason
    s.over_reason = GameOverReason.FIVE

    record_match(s, started_at=datetime.utcnow())
    assert s.recorded_match is False  # caller's responsibility; record_match doesn't set it
    s.recorded_match = True
    with Session(engine) as db:
        black_uid = s.players[ColorStr.BLACK].user_id
        u = db.exec(select(User).where(User.id == black_uid)).first()
        wins_after_one = u.wins
    assert wins_after_one == 1
