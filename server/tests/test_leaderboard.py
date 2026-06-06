"""GET /api/users/leaderboard — top players by wins."""
from __future__ import annotations

import uuid

from sqlmodel import Session

from omok_server.auth.security import hash_password
from omok_server.db.engine import engine
from omok_server.db.models import User


def _u() -> str:
    return f"u_{uuid.uuid4().hex[:8]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    return r.json()["access_token"], r.json()["user"]


def _make_user(*, username, wins, losses):
    with Session(engine) as db:
        u = User(username=username, password_hash=hash_password("pw1234"),
                 wins=wins, losses=losses)
        db.add(u); db.commit(); db.refresh(u)
        return u.id


def test_leaderboard_orders_by_wins_then_losses(client) -> None:
    tok, _ = _register(client)
    a = _make_user(username=_u(), wins=10, losses=2)
    b = _make_user(username=_u(), wins=10, losses=5)
    c = _make_user(username=_u(), wins=15, losses=0)
    r = client.get("/api/users/leaderboard?limit=50",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    entries = r.json()["entries"]
    # Find our three among the entries and verify the relative order.
    ids = [e["user_id"] for e in entries]
    pos = lambda uid: ids.index(uid)
    assert pos(c) < pos(a) < pos(b)  # c (15w) before a (10w/2L) before b (10w/5L)


def test_leaderboard_excludes_zero_game_users(client) -> None:
    tok, _ = _register(client)
    # A fresh user just registered above has 0 wins / 0 losses — should not appear.
    me_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["id"]
    r = client.get("/api/users/leaderboard",
                   headers={"Authorization": f"Bearer {tok}"})
    ids = [e["user_id"] for e in r.json()["entries"]]
    assert me_id not in ids


def test_leaderboard_ranks_are_consecutive_starting_at_1(client) -> None:
    tok, _ = _register(client)
    _make_user(username=_u(), wins=3, losses=1)
    _make_user(username=_u(), wins=2, losses=2)
    r = client.get("/api/users/leaderboard?limit=50",
                   headers={"Authorization": f"Bearer {tok}"})
    ranks = [e["rank"] for e in r.json()["entries"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_leaderboard_requires_auth(client) -> None:
    r = client.get("/api/users/leaderboard")
    assert r.status_code == 401


def test_leaderboard_respects_limit(client) -> None:
    tok, _ = _register(client)
    for i in range(5):
        _make_user(username=_u(), wins=i + 1, losses=0)
    r = client.get("/api/users/leaderboard?limit=3",
                   headers={"Authorization": f"Bearer {tok}"})
    entries = r.json()["entries"]
    assert len(entries) <= 3
