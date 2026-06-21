"""Presence panel: /ws/lobby pushes an online-users list on connect and
whenever anyone joins or leaves any channel.

Note on test style: TestClient.websocket_connect() returns a context manager
that synchronously cycles through accept → use → close. We use nested `with`
blocks rather than manual __enter__/__exit__ so the framework's lifecycle
hooks run correctly — manual lifecycle management is fragile here and tends
to hang on close.
"""
from __future__ import annotations

from tests.conftest import unique_username


def _register(client):
    name = unique_username()
    r = client.post("/api/auth/register", json={"username": name, "password": "pw1234"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["user"]


def _drain_until(ws, type_: str) -> dict:
    """Read frames until a `type_` frame arrives, return it."""
    while True:
        m = ws.receive_json()
        if m.get("type") == type_:
            return m


def test_lobby_sends_presence_on_connect_with_self(client) -> None:
    tok, user = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        presence = _drain_until(ws, "presence")
        usernames = [u["username"] for u in presence["users"]]
        assert user["username"] in usernames


def test_presence_includes_user_stats(client) -> None:
    tok, user = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={tok}") as ws:
        ws.receive_json()  # lobby_snapshot
        presence = _drain_until(ws, "presence")
        me = next(u for u in presence["users"] if u["user_id"] == user["id"])
        assert me["wins"] == 0
        assert me["losses"] == 0
        assert me["draws"] == 0
        assert me["username"] == user["username"]


def test_presence_pushed_when_second_user_connects(client) -> None:
    """When B connects, A's existing lobby socket receives a new presence
    frame containing both users."""
    a_tok, a = _register(client)
    b_tok, b = _register(client)
    with client.websocket_connect(f"/ws/lobby?token={a_tok}") as a_ws:
        a_ws.receive_json()  # lobby_snapshot
        _drain_until(a_ws, "presence")  # initial: just A

        with client.websocket_connect(f"/ws/lobby?token={b_tok}") as b_ws:
            b_ws.receive_json()  # B's lobby_snapshot
            updated = _drain_until(a_ws, "presence")
            ids = {u["user_id"] for u in updated["users"]}
            assert a["id"] in ids
            assert b["id"] in ids


def test_presence_pushed_when_user_disconnects(client) -> None:
    """A leaves their lobby socket → B's lobby socket receives a presence
    frame without A."""
    a_tok, a = _register(client)
    b_tok, b = _register(client)

    with client.websocket_connect(f"/ws/lobby?token={b_tok}") as b_ws:
        b_ws.receive_json()  # lobby_snapshot
        _drain_until(b_ws, "presence")  # initial: just B

        with client.websocket_connect(f"/ws/lobby?token={a_tok}") as a_ws:
            a_ws.receive_json()  # A's lobby_snapshot
            # Drain A's own buffered presence frame too — otherwise the
            # WebSocket close handshake at `with` exit can stall waiting
            # to deliver server frames the client hasn't read yet.
            _drain_until(a_ws, "presence")
            with_a = _drain_until(b_ws, "presence")
            assert {a["id"], b["id"]} == {u["user_id"] for u in with_a["users"]}
        # A's `with` block exited → A's socket closed → presence pushed to B.
        without_a = _drain_until(b_ws, "presence")
        ids = {u["user_id"] for u in without_a["users"]}
        assert a["id"] not in ids
        assert b["id"] in ids


def test_presence_users_sorted_by_username(client) -> None:
    """The presence list is sorted by username (case-insensitive)."""
    a_tok, _ = _register(client)
    b_tok, _ = _register(client)
    c_tok, _ = _register(client)

    def _drain_all(ws) -> None:
        """Drain every buffered frame for a socket so close can complete."""
        # Pull until we get a presence with all 3 users — that's the last
        # one the server will push without further input.
        target = 3
        while True:
            m = ws.receive_json()
            if m.get("type") == "presence" and len(m["users"]) >= target:
                return

    with client.websocket_connect(f"/ws/lobby?token={a_tok}") as a_ws, \
         client.websocket_connect(f"/ws/lobby?token={b_tok}") as b_ws, \
         client.websocket_connect(f"/ws/lobby?token={c_tok}") as c_ws:
        # Drain each socket up to its all-3-users presence frame so the
        # `with` exit close handshake doesn't stall on buffered server frames.
        _drain_all(a_ws)
        _drain_all(b_ws)
        # C's all-3 presence is also the answer we want to assert against.
        target = None
        while True:
            m = c_ws.receive_json()
            if m.get("type") == "presence" and len(m["users"]) >= 3:
                target = m
                break
        usernames = [u["username"] for u in target["users"]]
        assert usernames == sorted(usernames, key=str.lower)
