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
    return f"u{uuid.uuid4().hex[:10]}"


def _register(client):
    r = client.post("/api/auth/register", json={"username": _u(), "password": "pw1234"})
    return r.json()["access_token"], r.json()["user"]


def test_lobby_chat_round_trip(client) -> None:
    tok, user = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect) (no chat_history since buffer is empty)

        ws.send_text(json.dumps({"type": "chat", "text": "hello"}))
        msg = ws.receive_json()
        assert msg["type"] == "chat"
        assert msg["text"] == "hello"
        assert msg["username"] == user["username"]
        assert msg["user_id"] == user["id"]


def test_chat_empty_text_is_rejected(client) -> None:
    tok, _ = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect)
        ws.send_text(json.dumps({"type": "chat", "text": "   "}))
        # No broadcast — send a ping and verify only pong comes back.
        ws.send_text(json.dumps({"type": "ping"}))
        msg = ws.receive_json()
        assert msg["type"] == "pong"


def test_chat_history_includes_recent_messages(client) -> None:
    tok, _ = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect)
        ws.send_text(json.dumps({"type": "chat", "text": "first"}))
        ws.receive_json()  # the broadcast
        ws.send_text(json.dumps({"type": "chat", "text": "second"}))
        ws.receive_json()

    # New connection: lobby_snapshot then chat_history then presence.
    # chat_history goes before presence because handler sends them in that
    # order (chat_history before ws_registry.register, presence after).
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        history = ws.receive_json()
        assert history["type"] == "chat_history"
        ws.receive_json()  # presence frame
        texts = [m["text"] for m in history["messages"]]
        assert "first" in texts and "second" in texts


def test_chat_length_capped(client) -> None:
    tok, _ = _register(client)
    long_text = "a" * 500
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect)
        ws.send_text(json.dumps({"type": "chat", "text": long_text}))
        msg = ws.receive_json()
        assert msg["type"] == "chat"
        assert len(msg["text"]) <= 200


def test_chat_masks_profanity_with_asterisks(client) -> None:
    """Profane messages are still broadcast, but the bad word is replaced
    with asterisks on the server — the original text never reaches viewers."""
    tok, _ = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect)

        ws.send_text(json.dumps({"type": "chat", "text": "안녕"}))
        clean = ws.receive_json()
        assert clean["type"] == "chat"
        assert clean["text"] == "안녕"

        ws.send_text(json.dumps({"type": "chat", "text": "이 시발 진짜"}))
        dirty = ws.receive_json()
        assert dirty["type"] == "chat"
        # Bad word masked, surrounding text preserved.
        assert "시발" not in dirty["text"]
        assert dirty["text"] == "이 ** 진짜"


def test_chat_spam_triggers_3min_mute_and_system_announce(client) -> None:
    """Sending 6 messages within ~5s on one channel mutes the user for 3 min."""
    tok, user = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        ws.receive_json()  # presence frame (online users on connect)

        # First 5 messages broadcast normally.
        for i in range(5):
            ws.send_text(json.dumps({"type": "chat", "text": f"m{i}"}))
            ack = ws.receive_json()
            assert ack["type"] == "chat" and ack["text"] == f"m{i}"

        # 6th message trips the spam detector. We expect:
        #   (a) a system chat message announcing the mute, broadcast to everyone
        #   (b) an error response to the sender ("도배 감지 — 3분간...")
        # The order of (a) and (b) is implementation detail; assert both arrive.
        ws.send_text(json.dumps({"type": "chat", "text": "spam"}))
        received = [ws.receive_json(), ws.receive_json()]
        types = {m["type"]: m for m in received}
        assert "chat" in types and "error" in types
        sysmsg = types["chat"]
        assert sysmsg["is_system"] is True
        assert "도배" in sysmsg["text"] and user["username"] in sysmsg["text"]
        assert "도배" in types["error"]["message"]

        # A follow-up message during the mute is also blocked (different error).
        ws.send_text(json.dumps({"type": "chat", "text": "still here"}))
        blocked = ws.receive_json()
        assert blocked["type"] == "error"
        assert "채팅 금지 중" in blocked["message"]


def test_room_chat_isolated_from_lobby(client) -> None:
    """A message in a room should NOT show up on the lobby channel."""
    tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"},
                      headers={"Authorization": f"Bearer {tok}"}).json()["room_id"]

    # Send room chat.
    with client.websocket_connect(f"/ws/rooms/{rid}?token={tok}") as ws:
        ws.receive_json()  # room_state
        ws.send_text(json.dumps({"type": "chat", "text": "room-only"}))
        msg = ws.receive_json()
        assert msg["type"] == "chat" and msg["text"] == "room-only"

    # New lobby connection: empty lobby buffer → no chat_history at all.
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        first = ws.receive_json()
        assert first["type"] == "lobby_snapshot"
        ws.receive_json()  # presence frame
        # Send a ping to confirm there's nothing else queued.
        ws.send_text(json.dumps({"type": "ping"}))
        nxt = ws.receive_json()
        assert nxt["type"] == "pong"
