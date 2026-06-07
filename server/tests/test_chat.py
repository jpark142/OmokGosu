"""Chat across /ws/lobby, /ws/rooms/:id, /ws/games/:id.

Buffers are module-level (`omok_server.api.chat._buffers`) so each test starts
by clearing them — otherwise messages from earlier tests leak into history.
"""
from __future__ import annotations

import json
import uuid

import pytest

from omok_server.api import chat as chat_helpers


@pytest.fixture(autouse=True)
def _reset_chat_buffers():
    chat_helpers.clear_all_buffers()
    yield
    chat_helpers.clear_all_buffers()


def _u() -> str:
    return f"u_{uuid.uuid4().hex[:8]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    return r.json()["access_token"], r.json()["user"]


def test_lobby_chat_round_trip(client) -> None:
    tok, user = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # lobby_snapshot (no chat_history since buffer is empty)

        ws.send_text(json.dumps({"type": "chat", "text": "hello"}))
        msg = ws.receive_json()
        assert msg["type"] == "chat"
        assert msg["text"] == "hello"
        assert msg["username"] == user["username"]
        assert msg["user_id"] == user["id"]


def test_chat_empty_text_is_rejected(client) -> None:
    tok, _ = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.send_text(json.dumps({"type": "chat", "text": "   "}))
        # No broadcast — send a ping and verify only pong comes back.
        ws.send_text(json.dumps({"type": "ping"}))
        msg = ws.receive_json()
        assert msg["type"] == "pong"


def test_chat_history_includes_recent_messages(client) -> None:
    tok, _ = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.send_text(json.dumps({"type": "chat", "text": "first"}))
        ws.receive_json()  # the broadcast
        ws.send_text(json.dumps({"type": "chat", "text": "second"}))
        ws.receive_json()

    # New connection: lobby_snapshot then chat_history with both messages.
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # lobby_snapshot
        history = ws.receive_json()
        assert history["type"] == "chat_history"
        texts = [m["text"] for m in history["messages"]]
        assert "first" in texts and "second" in texts


def test_chat_length_capped(client) -> None:
    tok, _ = _register(client)
    long_text = "a" * 500
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.send_text(json.dumps({"type": "chat", "text": long_text}))
        msg = ws.receive_json()
        assert msg["type"] == "chat"
        assert len(msg["text"]) <= 200


def test_room_chat_isolated_from_lobby(client) -> None:
    """A message in a room should NOT show up on the lobby channel."""
    tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"},
                      headers={"Authorization": f"Bearer {tok}"}).json()["room_id"]

    # Send room chat.
    with client.websocket_connect(f"/ws/rooms/{rid}?token={tok}&client_version=1.0.0") as ws:
        ws.receive_json()  # room_state
        ws.send_text(json.dumps({"type": "chat", "text": "room-only"}))
        msg = ws.receive_json()
        assert msg["type"] == "chat" and msg["text"] == "room-only"

    # New lobby connection: empty lobby buffer → no chat_history at all.
    with client.websocket_connect(f"/ws/lobby?token={tok}&client_version=1.0.0") as ws:
        first = ws.receive_json()
        assert first["type"] == "lobby_snapshot"
        # Send a ping to confirm there's nothing else queued.
        ws.send_text(json.dumps({"type": "ping"}))
        nxt = ws.receive_json()
        assert nxt["type"] == "pong"
