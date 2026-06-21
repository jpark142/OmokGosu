"""Live spectator mode on /ws/games/{game_id}.

A non-participant connecting to a PLAYING game gets read-only access plus
chat. Their chat messages broadcast with role="spectator" so the client
can render the "[관전]" prefix. Move/resign messages from a spectator are
rejected. Joining/leaving rebroadcasts the state with the updated spectator
list."""
from __future__ import annotations

import json
import uuid


def _u() -> str:
    return f"u{uuid.uuid4().hex[:10]}"


def _register(client) -> tuple[str, dict, str]:
    username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["user"], username


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _recv_skip_chat(ws):
    while True:
        msg = ws.receive_json()
        if msg.get("type") in ("chat", "chat_history"):
            continue
        return msg


def _start_room_game(client, host_tok: str, guest_tok: str) -> tuple[str, str]:
    """Spin up a room, ready+start, return (room_id, game_id)."""
    rid = client.post("/api/rooms", json={"title": "spec"}, headers=_hdr(host_tok)).json()["room_id"]
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
    return rid, game_id


def test_third_user_can_spectate_running_game(client) -> None:
    host_tok, _h, _ = _register(client)
    guest_tok, _g, _ = _register(client)
    _rid, gid = _start_room_game(client, host_tok, guest_tok)

    spec_tok, spec, _ = _register(client)
    with client.websocket_connect(f"/ws/games/{gid}?token={spec_tok}") as ws:
        state = _recv_skip_chat(ws)
        assert state["type"] == "state"
        # Spectator should now appear in the broadcast list.
        # Spectators list reaches the spectator either in their first state
        # frame or as the rebroadcast that follows the join — both count.
        if not state.get("spectators"):
            state = _recv_skip_chat(ws)
        assert any(s["user_id"] == spec["id"] for s in state["spectators"])


def test_spectator_chat_carries_role(client) -> None:
    host_tok, host, _ = _register(client)
    guest_tok, _g, _ = _register(client)
    _rid, gid = _start_room_game(client, host_tok, guest_tok)
    spec_tok, _spec, _ = _register(client)

    with client.websocket_connect(f"/ws/games/{gid}?token={host_tok}") as host_ws:
        _recv_skip_chat(host_ws)  # state
        with client.websocket_connect(f"/ws/games/{gid}?token={spec_tok}") as spec_ws:
            _recv_skip_chat(spec_ws)  # state (may include join rebroadcast)
            spec_ws.send_text(json.dumps({"type": "chat", "text": "hi"}))

            # Host should receive the chat with role="spectator". Drain
            # state rebroadcasts caused by the spectator joining.
            for _ in range(10):
                msg = host_ws.receive_json()
                if msg["type"] == "chat" and msg["text"] == "hi":
                    assert msg["role"] == "spectator"
                    assert msg["user_id"] != host["id"]
                    return
            assert False, "spectator chat never reached host"


def _drain_until(ws, types: tuple[str, ...]):
    """Skip past chat / state rebroadcasts that arrive before the message
    we're actually waiting on (e.g. an `error` reply)."""
    while True:
        msg = ws.receive_json()
        if msg.get("type") in types:
            return msg


def test_spectator_move_and_resign_rejected(client) -> None:
    host_tok, _h, _ = _register(client)
    guest_tok, _g, _ = _register(client)
    _rid, gid = _start_room_game(client, host_tok, guest_tok)
    spec_tok, _spec, _ = _register(client)

    with client.websocket_connect(f"/ws/games/{gid}?token={spec_tok}") as ws:
        _recv_skip_chat(ws)
        ws.send_text(json.dumps({"type": "move", "r": 7, "c": 7}))
        msg = _drain_until(ws, ("error",))
        assert "관전자" in msg["message"]

        ws.send_text(json.dumps({"type": "resign"}))
        msg = _drain_until(ws, ("error",))
        assert msg["type"] == "error"


def test_player_is_not_demoted_to_spectator(client) -> None:
    """A participant reconnecting (e.g. refresh) should remain a player and
    must not appear in the spectators list."""
    host_tok, host, _ = _register(client)
    guest_tok, _g, _ = _register(client)
    _rid, gid = _start_room_game(client, host_tok, guest_tok)

    with client.websocket_connect(f"/ws/games/{gid}?token={host_tok}") as ws:
        state = _recv_skip_chat(ws)
        assert state["type"] == "state"
        assert all(s["user_id"] != host["id"] for s in state.get("spectators", []))
