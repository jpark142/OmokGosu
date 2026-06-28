"""GET /api/matches/:id — replay viewer backing data."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlmodel import Session

from omok_server.db.engine import engine
from omok_server.db.models import Match


def _u() -> str:
    return f"u{uuid.uuid4().hex[:10]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    return r.json()["access_token"], r.json()["user"]


def _make_match(*, black_uid, white_uid, winner_uid, moves, is_ai=False):
    now = datetime.utcnow()
    with Session(engine) as db:
        m = Match(
            game_id="g_" + uuid.uuid4().hex[:6],
            black_user_id=black_uid,
            white_user_id=white_uid,
            winner_user_id=winner_uid,
            over_reason="FIVE",
            started_at=now,
            ended_at=now,
            move_count=len(moves),
            is_ai_game=is_ai,
            moves_json=json.dumps(moves),
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m.id


def test_get_match_returns_moves_in_order(client) -> None:
    tok_a, alice = _register(client)
    tok_b, bob = _register(client)

    moves = [
        {"r": 7, "c": 7, "color": "BLACK"},
        {"r": 7, "c": 8, "color": "WHITE"},
        {"r": 8, "c": 7, "color": "BLACK"},
    ]
    mid = _make_match(black_uid=alice["id"], white_uid=bob["id"],
                      winner_uid=alice["id"], moves=moves)

    r = client.get(f"/api/matches/{mid}", headers={"Authorization": f"Bearer {tok_a}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["match_id"] == mid
    assert body["black_username"] == alice["username"]
    assert body["white_username"] == bob["username"]
    assert body["winner_color"] == "BLACK"
    assert body["move_count"] == 3
    assert len(body["moves"]) == 3
    assert body["moves"][0]["r"] == 7 and body["moves"][0]["color"] == "BLACK"


def test_non_participant_can_view(client) -> None:
    """Replays are public to any logged-in user — a non-participant gets 200,
    not 403. (Match history is already public via the user-profile list.)"""
    tok_a, alice = _register(client)
    tok_b, bob = _register(client)
    tok_c, _ = _register(client)  # not in the match

    mid = _make_match(black_uid=alice["id"], white_uid=bob["id"],
                      winner_uid=alice["id"], moves=[])
    r = client.get(f"/api/matches/{mid}", headers={"Authorization": f"Bearer {tok_c}"})
    assert r.status_code == 200, r.text
    assert r.json()["match_id"] == mid


def test_unknown_match_404(client) -> None:
    tok, _ = _register(client)
    r = client.get("/api/matches/999999", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_unauth_401(client) -> None:
    r = client.get("/api/matches/1")
    assert r.status_code == 401


def test_ai_game_winner_color_inferred(client) -> None:
    """When AI wins (winner_user_id is NULL), API infers the winning color from
    which slot is the AI (NULL user_id)."""
    tok, human = _register(client)
    # Human plays BLACK, AI (NULL user_id) plays WHITE and wins.
    mid = _make_match(
        black_uid=human["id"], white_uid=None,
        winner_uid=None,  # AI win — no user
        moves=[{"r": 7, "c": 7, "color": "BLACK"}], is_ai=True,
    )
    r = client.get(f"/api/matches/{mid}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["winner_color"] == "WHITE"  # the AI slot
    assert body["white_username"] == "AI"
    assert body["is_ai_game"] is True
