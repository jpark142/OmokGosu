"""Auth REST endpoint tests."""
from __future__ import annotations

import uuid


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def test_register_login_me_happy_path(client) -> None:
    username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["username"] == username
    assert body["user"]["wins"] == 0 and body["user"]["losses"] == 0
    assert len(body["access_token"]) > 10

    r2 = client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
    assert r2.status_code == 200, r2.text
    token = r2.json()["access_token"]

    r3 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    assert r3.json()["username"] == username


def test_register_duplicate_username_returns_409(client) -> None:
    username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201
    r2 = client.post("/api/auth/register", json={"username": username, "password": "other"})
    assert r2.status_code == 409


def test_login_wrong_password_returns_401(client) -> None:
    username = _u()
    client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    r = client.post("/api/auth/login", json={"username": username, "password": "wrongpw"})
    assert r.status_code == 401


def test_login_unknown_user_returns_401(client) -> None:
    r = client.post("/api/auth/login", json={"username": _u(), "password": "anything"})
    assert r.status_code == 401


def test_me_requires_token(client) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_rejects_garbage_token(client) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401


def test_register_validates_short_password(client) -> None:
    r = client.post("/api/auth/register", json={"username": _u(), "password": "ab"})
    assert r.status_code == 422  # Pydantic min_length=4


def test_me_returns_current_room_id(client) -> None:
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    tok = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}

    # No room yet → null.
    assert client.get("/api/auth/me", headers=hdr).json()["current_room_id"] is None

    # Create a room → /me reports it.
    rid = client.post("/api/rooms", json={"title": "in-progress"}, headers=hdr).json()["room_id"]
    assert client.get("/api/auth/me", headers=hdr).json()["current_room_id"] == rid

    # Leave → back to null.
    client.post(f"/api/rooms/{rid}/leave", headers=hdr)
    assert client.get("/api/auth/me", headers=hdr).json()["current_room_id"] is None


def test_login_returns_current_room_id(client) -> None:
    username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    tok = r.json()["access_token"]
    rid = client.post("/api/rooms", json={"title": "x"}, headers={"Authorization": f"Bearer {tok}"}).json()["room_id"]

    # Login again — should surface the existing room.
    r2 = client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
    assert r2.json()["user"]["current_room_id"] == rid


def test_relogin_invalidates_previous_token(client) -> None:
    """The newer login should retire the older token (single-session policy)."""
    username = _u()
    client.post("/api/auth/register", json={"username": username, "password": "pw1234"})

    r1 = client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
    tok1 = r1.json()["access_token"]

    # Old token still works right after first login.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok1}"}).status_code == 200

    # Second login from "another device" — old token must now be rejected.
    r2 = client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
    tok2 = r2.json()["access_token"]
    assert tok2 != tok1

    stale = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok1}"})
    assert stale.status_code == 401
    assert stale.json()["detail"] == "session displaced"

    # New token works.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok2}"}).status_code == 200


def test_register_then_relogin_invalidates_register_token(client) -> None:
    """The convenience token from /register is invalidated by the first /login."""
    username = _u()
    r0 = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    register_tok = r0.json()["access_token"]
    # Register-issued token works.
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {register_tok}"}
    ).status_code == 200
    # First subsequent login retires it.
    client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {register_tok}"}
    ).status_code == 401
