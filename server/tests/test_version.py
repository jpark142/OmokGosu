"""/api/version endpoint + X-Client-Version middleware + WS 4426 gate.

Resolution of `SERVER_VERSION` and `MIN_CLIENT_VERSION` is dynamic so this
test file survives version bumps without manual edits — see
[[feedback_version_bump]] in the agent's memory for the policy.
"""
from __future__ import annotations

import uuid

from starlette.websockets import WebSocketDisconnect

from omok_server.version import MIN_CLIENT_VERSION, SERVER_VERSION

# A deliberately-ancient version string used everywhere we want to assert the
# gate kicks in. Stays below any plausible MIN_CLIENT_VERSION the project will
# ever ship.
_OUTDATED = "0.0.1"


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _create_game_id(client, tok: str) -> str:
    r = client.post(
        "/api/games",
        json={"mode": "hva", "ai_level": "random"},
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": SERVER_VERSION},
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


# ----- /api/health endpoint (Fly.io liveness probe) -----

def test_health_endpoint_returns_ok_json(client) -> None:
    """Fly.io's health check hits GET /api/health every 30s. The handler
    must stay cheap and dependency-free so a transient DB blip doesn't
    cause Fly to cycle the machine."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == SERVER_VERSION


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
    assert body["version"] == SERVER_VERSION
    assert body["min_client_version"] == MIN_CLIENT_VERSION


def test_version_endpoint_is_exempt_from_gate(client) -> None:
    """Even an ancient client should be able to read /api/version so it can
    learn what to upgrade to."""
    r = client.get("/api/version", headers={"X-Client-Version": _OUTDATED})
    assert r.status_code == 200


# ----- X-Client-Version middleware -----

def test_missing_header_is_allowed(client) -> None:
    """Lenient policy: no header → pass (curl/debug/external tools)."""
    r = client.get("/api/health")
    assert r.status_code == 200


def test_compatible_version_passes(client) -> None:
    r = client.get("/api/health", headers={"X-Client-Version": MIN_CLIENT_VERSION})
    assert r.status_code == 200


def test_newer_client_passes(client) -> None:
    """A client ahead of the server is fine — the server only enforces a floor."""
    r = client.get("/api/health", headers={"X-Client-Version": "999.0.0"})
    assert r.status_code == 200


def test_outdated_client_returns_426(client) -> None:
    r = client.get("/api/health", headers={"X-Client-Version": _OUTDATED})
    assert r.status_code == 426
    body = r.json()
    assert body["min_client_version"] == MIN_CLIENT_VERSION
    assert body["server_version"] == SERVER_VERSION
    assert r.headers.get("X-Min-Client-Version") == MIN_CLIENT_VERSION


def test_malformed_version_passes(client) -> None:
    """Junk version strings are treated as 'unknown' → pass (lenient)."""
    r = client.get("/api/health", headers={"X-Client-Version": "not-a-version"})
    assert r.status_code == 200


def test_gate_applies_to_authenticated_endpoints(client) -> None:
    tok = _register(client)
    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tok}", "X-Client-Version": _OUTDATED},
    )
    assert r.status_code == 426


# ----- WS 4426 gate -----

def test_ws_outdated_client_closes_4426(client) -> None:
    tok = _register(client)
    gid = _create_game_id(client, tok)

    try:
        with client.websocket_connect(
            f"/ws/games/{gid}?token={tok}&client_version={_OUTDATED}"
        ) as ws:
            ws.receive_json()
        raise AssertionError("expected close")
    except WebSocketDisconnect as e:
        assert e.code == 4426


def test_ws_compatible_client_handshakes(client) -> None:
    tok = _register(client)
    gid = _create_game_id(client, tok)

    with client.websocket_connect(
        f"/ws/games/{gid}?token={tok}&client_version={MIN_CLIENT_VERSION}"
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"


def test_ws_missing_version_is_allowed(client) -> None:
    """Same lenient policy as HTTP: missing version param → pass."""
    tok = _register(client)
    gid = _create_game_id(client, tok)

    with client.websocket_connect(f"/ws/games/{gid}?token={tok}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
