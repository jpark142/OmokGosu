"""WebSocket force-close on login (single-session policy follow-through).

Before this feature, /login retired the previous token but any WS already
accepted with that token stayed open until its next message round-tripped.
These tests assert that a second login *actively* closes the prior session's
sockets across all three channels (lobby / room / game)."""
from __future__ import annotations

import json
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect


def _u() -> str:
    return f"u{uuid.uuid4().hex[:10]}"


def _register(client) -> tuple[str, dict, str]:
    """Returns (token, user, username)."""
    username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["user"], username


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _recv_skip_chat(ws):
    """Drain background frames (chat, chat_history, presence) until a
    test-relevant message arrives."""
    while True:
        msg = ws.receive_json()
        if msg.get("type") in ("chat", "chat_history", "presence"):
            continue
        return msg


def test_login_closes_existing_lobby_ws(client) -> None:
    tok, _user, username = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        # Drain the initial lobby_snapshot.
        _recv_skip_chat(ws)

        # Second login from "another device" — server should force-close
        # the existing lobby socket with code 4401.
        r = client.post("/api/auth/login", json={"username": username, "password": "pw1234"})
        assert r.status_code == 200

        with pytest.raises(WebSocketDisconnect) as exc:
            # Drain whatever the server sends; the close should arrive
            # promptly with the displaced code.
            while True:
                ws.receive_json()
        assert exc.value.code == 4401


def test_login_closes_existing_room_ws(client) -> None:
    tok, user, username = _register(client)
    rid = client.post("/api/rooms", json={"title": "x"}, headers=_hdr(tok)).json()["room_id"]
    with client.websocket_connect(f"/ws/rooms/{rid}?token={tok}") as ws:
        _recv_skip_chat(ws)  # initial room_state

        client.post("/api/auth/login", json={"username": username, "password": "pw1234"})

        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                ws.receive_json()
        assert exc.value.code == 4401


def test_login_closes_existing_game_ws(client) -> None:
    """End-to-end: host + guest start a game, then host re-logs in. The host's
    open game WS should get a 4401 close from the registry."""
    host_tok, host, host_name = _register(client)
    guest_tok, _guest, _guest_name = _register(client)
    rid = client.post("/api/rooms", json={"title": "g"}, headers=_hdr(host_tok)).json()["room_id"]
    client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok))

    with client.websocket_connect(f"/ws/rooms/{rid}?token={guest_tok}") as gw:
        _recv_skip_chat(gw)
        gw.send_text(json.dumps({"type": "ready", "value": True}))
        _recv_skip_chat(gw)

    game_id: str | None = None
    with client.websocket_connect(f"/ws/rooms/{rid}?token={host_tok}") as hw:
        _recv_skip_chat(hw)
        hw.send_text(json.dumps({"type": "start"}))
        for _ in range(8):
            msg = _recv_skip_chat(hw)
            if msg["type"] == "room_game_started":
                game_id = msg["game_id"]
                break
    assert game_id is not None

    with client.websocket_connect(f"/ws/games/{game_id}?token={host_tok}") as gws:
        _recv_skip_chat(gws)  # initial state

        client.post("/api/auth/login", json={"username": host_name, "password": "pw1234"})

        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                gws.receive_json()
        assert exc.value.code == 4401


def test_other_user_login_does_not_close_my_ws(client) -> None:
    a_tok, _a, _ = _register(client)
    _b_tok, _b, b_name = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={a_tok}") as ws:
        _recv_skip_chat(ws)
        # B's login must not touch A's socket.
        r = client.post("/api/auth/login", json={"username": b_name, "password": "pw1234"})
        assert r.status_code == 200
        # Send a ping — A's socket should still be alive and answer pong.
        ws.send_text(json.dumps({"type": "ping"}))
        msg = _recv_skip_chat(ws)
        assert msg["type"] == "pong"
