"""Recent-matches endpoint backing the hover card."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Session

from omok_server.db.engine import engine
from omok_server.db.models import Match


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def _register(client, username=None):
    if username is None:
        username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    return r.json()["access_token"], r.json()["user"]


def test_recent_matches_empty(client) -> None:
    tok, user = _register(client)
    r = client.get(
        f"/api/users/{user['id']}/recent-matches",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == user["id"]
    assert body["matches"] == []


def test_recent_matches_includes_recent_and_marks_winner(client) -> None:
    tok_a, alice = _register(client)
    tok_b, bob = _register(client)

    # Insert two synthetic Match rows: alice wins one, bob wins the other.
    now = datetime.utcnow()
    with Session(engine) as db:
        db.add(Match(
            game_id="g1", black_user_id=alice["id"], white_user_id=bob["id"],
            winner_user_id=alice["id"], over_reason="FIVE",
            started_at=now, ended_at=now, move_count=37,
        ))
        db.add(Match(
            game_id="g2", black_user_id=bob["id"], white_user_id=alice["id"],
            winner_user_id=bob["id"], over_reason="RESIGN",
            started_at=now, ended_at=now, move_count=12,
        ))
        db.commit()

    r = client.get(
        f"/api/users/{alice['id']}/recent-matches",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert r.status_code == 200
    matches = r.json()["matches"]
    assert len(matches) == 2
    by_game = {(m["over_reason"], m["your_color"]): m for m in matches}
    assert by_game[("FIVE", "BLACK")]["you_won"] is True
    assert by_game[("FIVE", "BLACK")]["opponent_username"] == bob["username"]
    assert by_game[("RESIGN", "WHITE")]["you_won"] is False
    assert by_game[("RESIGN", "WHITE")]["opponent_username"] == bob["username"]


def test_recent_matches_ai_game_marks_opponent_null(client) -> None:
    tok, user = _register(client)
    now = datetime.utcnow()
    with Session(engine) as db:
        db.add(Match(
            game_id="g_ai", black_user_id=user["id"], white_user_id=None,
            winner_user_id=user["id"], over_reason="FIVE",
            started_at=now, ended_at=now, move_count=20, is_ai_game=True,
        ))
        db.commit()

    r = client.get(
        f"/api/users/{user['id']}/recent-matches",
        headers={"Authorization": f"Bearer {tok}"},
    )
    matches = r.json()["matches"]
    ai_match = next(m for m in matches if m["is_ai_game"])
    assert ai_match["opponent_username"] is None
    assert ai_match["opponent_user_id"] is None


def test_recent_matches_unknown_user_returns_404(client) -> None:
    tok, _ = _register(client)
    r = client.get("/api/users/999999/recent-matches", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_recent_matches_requires_auth(client) -> None:
    r = client.get("/api/users/1/recent-matches")
    assert r.status_code == 401
