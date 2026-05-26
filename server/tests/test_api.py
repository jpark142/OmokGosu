"""End-to-end REST + WebSocket tests using FastAPI's TestClient."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from omok_server.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_create_and_fetch_game() -> None:
    r = client.post("/api/games", json={"mode": "hvh"})
    assert r.status_code == 200
    data = r.json()
    assert "game_id" in data
    gid = data["game_id"]

    r2 = client.get(f"/api/games/{gid}")
    assert r2.status_code == 200
    state = r2.json()
    assert state["board_size"] == 15
    assert state["to_move"] == "BLACK"
    assert state["move_number"] == 0


def test_ws_initial_state_and_move() -> None:
    r = client.post("/api/games", json={"mode": "hvh"})
    gid = r.json()["game_id"]

    with client.websocket_connect(f"/ws/games/{gid}") as ws:
        # First message is initial state.
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["move_number"] == 0
        assert msg["to_move"] == "BLACK"

        ws.send_text(json.dumps({"type": "move", "r": 7, "c": 7}))

        # Server sends move_applied + state. Collect the next two messages
        # (skip any timer_tick that may slip in between).
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


def test_ws_rejects_forbidden_double_three() -> None:
    r = client.post("/api/games", json={"mode": "hvh"})
    gid = r.json()["game_id"]

    setup = [
        (7, 5, "BLACK"), (0, 0, "WHITE"),
        (7, 6, "BLACK"), (0, 1, "WHITE"),
        (5, 7, "BLACK"), (0, 2, "WHITE"),
        (6, 7, "BLACK"), (0, 3, "WHITE"),
    ]
    with client.websocket_connect(f"/ws/games/{gid}") as ws:
        ws.receive_json()  # initial state
        for (rr, cc, _color) in setup:
            ws.send_text(json.dumps({"type": "move", "r": rr, "c": cc}))
            # drain to next state (skip move_applied / ticks)
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "state":
                    break

        # Now black to move; try the double-three square.
        ws.send_text(json.dumps({"type": "move", "r": 7, "c": 7}))
        # Should receive a forbidden_move_rejected.
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "forbidden_move_rejected":
                assert msg["reason"] == "DOUBLE_THREE"
                return
        raise AssertionError("expected forbidden_move_rejected")
