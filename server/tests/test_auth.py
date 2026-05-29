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
