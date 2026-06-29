"""End-to-end REST + WebSocket tests using FastAPI's TestClient.

Phase 3A: REST + WS now require auth, so each test starts by registering a
fresh user via the `auth_client` fixture (defined in conftest.py).
"""
from __future__ import annotations

import json


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_create_game_requires_auth(client) -> None:
    r = client.post("/api/games", json={"mode": "hvh"})
    assert r.status_code == 401


def test_create_and_fetch_game(auth_client) -> None:
    client, token, _ = auth_client
    r = client.post("/api/games", json={"mode": "hvh"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "game_id" in data
    gid = data["game_id"]

    r2 = client.get(f"/api/games/{gid}")
    assert r2.status_code == 200
    state = r2.json()
    assert state["board_size"] == 15
    assert state["to_move"] == "BLACK"
    assert state["move_number"] == 0


def test_ws_rejects_missing_token(auth_client) -> None:
    client, _, _ = auth_client
    r = client.post("/api/games", json={"mode": "hvh"})
    gid = r.json()["game_id"]

    # TestClient raises WebSocketDisconnect when server closes during handshake.
    from starlette.websockets import WebSocketDisconnect
    try:
        with client.websocket_connect(f"/ws/games/{gid}") as ws:
            ws.receive_json()
        raise AssertionError("expected close")
    except WebSocketDisconnect as e:
        assert e.code == 4401


def test_ws_initial_state_and_move(auth_client) -> None:
    client, token, _ = auth_client
    r = client.post("/api/games", json={"mode": "hvh"})
    gid = r.json()["game_id"]

    with client.websocket_connect(f"/ws/games/{gid}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["move_number"] == 0
        assert msg["to_move"] == "BLACK"

        ws.send_text(json.dumps({"type": "move", "r": 7, "c": 7}))

        applied = None
        state = None
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "move_applied":
                applied = msg
            elif msg["type"] == "state":
                state = msg
                break
        assert applied is not None
        assert applied["move"]["r"] == 7 and applied["move"]["c"] == 7
        assert applied["move"]["color"] == "BLACK"
        assert state is not None
        assert state["to_move"] == "WHITE"


def test_ws_rejects_forbidden_double_three(auth_client) -> None:
    client, token, _ = auth_client
    r = client.post("/api/games", json={"mode": "hvh"})
    gid = r.json()["game_id"]

    setup = [
        (7, 5, "BLACK"), (0, 0, "WHITE"),
        (7, 6, "BLACK"), (0, 1, "WHITE"),
        (5, 7, "BLACK"), (0, 2, "WHITE"),
        (6, 7, "BLACK"), (0, 3, "WHITE"),
    ]
    with client.websocket_connect(f"/ws/games/{gid}?token={token}") as ws:
        ws.receive_json()  # initial state
        for (rr, cc, _color) in setup:
            ws.send_text(json.dumps({"type": "move", "r": rr, "c": cc}))
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "state":
                    break

        ws.send_text(json.dumps({"type": "move", "r": 7, "c": 7}))
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "forbidden_move_rejected":
                assert msg["reason"] == "DOUBLE_THREE"
                return
        raise AssertionError("expected forbidden_move_rejected")


def test_forbidden_squares_only_visible_to_black(auth_client) -> None:
    """Black's forbidden-move (금수) markers must reach the black player only —
    never white or spectators. Regression guard for the state-broadcast leak."""
    from fastapi.testclient import TestClient

    from omok_server.main import app
    from tests.conftest import unique_username

    client, token, _ = auth_client
    # We need the creating user to hold BLACK so we can assert they DO see the
    # markers. Colour is assigned randomly, so retry until we land on BLACK.
    gid = None
    for _ in range(30):
        r = client.post("/api/games", json={"mode": "hvh"})
        data = r.json()
        if data["your_color"] == "BLACK":
            gid = data["game_id"]
            break
    assert gid is not None, "never got assigned BLACK"

    # Build a position where (7,7) is a 3-3 forbidden point with BLACK to move.
    setup = [
        (7, 5), (0, 0),
        (7, 6), (0, 1),
        (5, 7), (0, 2),
        (6, 7), (0, 3),
    ]
    with client.websocket_connect(f"/ws/games/{gid}?token={token}") as ws:
        ws.receive_json()  # initial state
        for (rr, cc) in setup:
            ws.send_text(json.dumps({"type": "move", "r": rr, "c": cc}))
            for _ in range(5):
                if ws.receive_json()["type"] == "state":
                    break

    # Black player (the creator) sees the forbidden squares...
    state_black = client.get(f"/api/games/{gid}").json()
    assert state_black["to_move"] == "BLACK"
    assert [7, 7] in [list(sq) for sq in state_black["forbidden_squares"]]

    # ...but a different, non-black user (spectator / opponent) does not.
    other = TestClient(app)
    uname = unique_username("w")
    rr = other.post("/api/auth/register", json={"username": uname, "password": "pw1234"})
    other.headers.update({"Authorization": f"Bearer {rr.json()['access_token']}"})
    state_other = other.get(f"/api/games/{gid}").json()
    assert state_other["to_move"] == "BLACK"
    assert state_other["forbidden_squares"] == []
