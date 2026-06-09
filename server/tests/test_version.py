"""/api/version endpoint + X-Client-Version middleware + WS 4426 gate."""
from __future__ import annotations

import uuid

from starlette.websockets import WebSocketDisconnect


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


# ----- /api/health endpoint (Fly.io liveness probe) -----

def test_health_endpoint_returns_ok_json(client) -> None:
    """Fly.io's health check hits GET /api/health every 30s. The handler
    must stay cheap and dependency-free so a transient DB blip doesn't
    cause Fly to cycle the machine."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"


def test_health_endpoint_no_auth_no_version_header(client) -> None:
    """Same lenient policy as /api/version — probes shouldn't fail on
    missing X-Client-Version."""
    r = client.get("/api/health", headers={})
    assert r.status_code == 200


# ----- /api/version endpoint -----

def test_version_endpoint_unauthenticated(client) -> None:
    r = client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.0.0"
    assert body["min_client_version"] == "1.0.0"


def test_version_endpoint_is_exempt_from_gate(client) -> None:
    """Even an ancient client should be able to read /api/version so it can
    learn what to upgrade to."""
    r = client.get("/api/version", headers={"X-Client-Version": "0.0.1"})
    assert r.status_code == 200


# ----- X-Client-Version middleware -----

def test_missing_header_is_allowed(client) -> None:
    """Lenient policy: no header → pass (curl/debug/external tools)."""
    r = client.get("/api/health")
    assert r.status_code == 200


def test_compatible_version_passes(client) -> None:
    r = client.get("/api/health", headers={"X-Client-Version": "1.0.0"})
    assert r.status_code == 200


def test_newer_client_passes(client) -> None:
    """A client ahead of the server is fine — the server only enforces a floor."""
    r = client.get("/api/health", headers={"X-Client-Version": "2.5.0"})
    assert r.status_code == 200


def test_outdated_client_returns_426(client) -> None:
    r = client.get("/api/health", headers={"X-Client-Version": "0.9.0"})
    assert r.status_code == 426
    body = r.json()
    assert body["min_client_version"] == "1.0.0"
    assert body["server_version"] == "1.0.0"
    assert r.headers.get("X-Min-Client-Version") == "1.0.0"


def test_malformed_version_passes(client) -> None:
    """Junk version strings are treated as 'unknown' → pass (lenient)."""
    r = client.get("/api/health", headers={"X-Client-Version": "not-a-version"})
    assert r.status_code == 200


def test_gate_applies_to_authenticated_endpoints(client) -> None:
    tok = _register(client)
    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": "0.5.0"},
    )
    assert r.status_code == 426


# ----- WS 4426 gate -----

def test_ws_outdated_client_closes_4426(client) -> None:
    tok = _register(client)
    # Create a game (HVA) to have a game_id to connect to.
    r = client.post(
        "/api/games",
        json={"mode": "hva", "ai_level": "random"},
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": "1.0.0"},
    )
    gid = r.json()["game_id"]

    try:
        with client.websocket_connect(
            f"/ws/games/{gid}?token={tok}&client_version=0.5.0"
        ) as ws:
            ws.receive_json()
        raise AssertionError("expected close")
    except WebSocketDisconnect as e:
        assert e.code == 4426


def test_ws_compatible_client_handshakes(client) -> None:
    tok = _register(client)
    r = client.post(
        "/api/games",
        json={"mode": "hva", "ai_level": "random"},
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": "1.0.0"},
    )
    gid = r.json()["game_id"]

    with client.websocket_connect(
        f"/ws/games/{gid}?token={tok}&client_version=1.0.0"
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"


def test_ws_missing_version_is_allowed(client) -> None:
    """Same lenient policy as HTTP: missing version param → pass."""
    tok = _register(client)
    r = client.post(
        "/api/games",
        json={"mode": "hva", "ai_level": "random"},
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": "1.0.0"},
    )
    gid = r.json()["game_id"]

    with client.websocket_connect(f"/ws/games/{gid}?token={tok}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
