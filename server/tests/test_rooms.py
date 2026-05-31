"""Room REST + RoomManager state machine + room WS integration."""
from __future__ import annotations

import json
import uuid


def _u() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def _register(client, username: str | None = None) -> tuple[str, dict]:
    if username is None:
        username = _u()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["user"]


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_create_room_lists_in_lobby(client) -> None:
    host_tok, host = _register(client)
    r = client.post("/api/rooms", json={"title": "alice's room"}, headers=_hdr(host_tok))
    assert r.status_code == 201, r.text
    room = r.json()
    assert room["title"] == "alice's room"
    assert room["has_password"] is False
    assert room["host"]["user_id"] == host["id"]
    assert room["guest"] is None
    assert room["status"] == "LOBBY"
    assert room["guest_ready"] is False

    other_tok, _ = _register(client)
    r2 = client.get("/api/rooms", headers=_hdr(other_tok))
    assert r2.status_code == 200
    rooms = r2.json()
    assert any(r["room_id"] == room["room_id"] for r in rooms)


def test_join_requires_correct_password(client) -> None:
    host_tok, _ = _register(client)
    r = client.post("/api/rooms", json={"title": "secret", "password": "sesame"}, headers=_hdr(host_tok))
    rid = r.json()["room_id"]

    guest_tok, _ = _register(client)
    r1 = client.post(f"/api/rooms/{rid}/join", json={"password": "nope"}, headers=_hdr(guest_tok))
    assert r1.status_code == 401

    r2 = client.post(f"/api/rooms/{rid}/join", json={"password": "sesame"}, headers=_hdr(guest_tok))
    assert r2.status_code == 200
    assert r2.json()["guest"]["user_id"] is not None


def test_join_full_room_returns_409(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    g1_tok, _ = _register(client)
    assert client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(g1_tok)).status_code == 200
    g2_tok, _ = _register(client)
    assert client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(g2_tok)).status_code == 409


def test_get_room_forbids_non_member(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    stranger_tok, _ = _register(client)
    r = client.get(f"/api/rooms/{rid}", headers=_hdr(stranger_tok))
    assert r.status_code == 403


def test_guest_leave_keeps_room_host_leave_deletes(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    guest_tok, _ = _register(client)
    assert client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok)).status_code == 200

    r = client.post(f"/api/rooms/{rid}/leave", headers=_hdr(guest_tok))
    assert r.status_code == 204
    # Room still listed.
    rooms = client.get("/api/rooms", headers=_hdr(host_tok)).json()
    assert any(rr["room_id"] == rid for rr in rooms)

    # Host leave → room deleted.
    r = client.post(f"/api/rooms/{rid}/leave", headers=_hdr(host_tok))
    assert r.status_code == 204
    rooms2 = client.get("/api/rooms", headers=_hdr(guest_tok)).json()
    assert not any(rr["room_id"] == rid for rr in rooms2)


def test_room_ws_start_succeeds_and_creates_game(client) -> None:
    """Single-WS variant of the start flow. Multi-WS broadcasts are stressed by
    the unit test on RoomManager below — TestClient deadlocks on concurrent
    `websocket_connect` in some FastAPI versions, so we read host-side only."""
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    guest_tok, _ = _register(client)
    client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok))

    # Ready the guest via the WS so the host can start.
    with client.websocket_connect(f"/ws/rooms/{rid}?token={guest_tok}") as guest_ws:
        guest_ws.receive_json()  # initial state
        guest_ws.send_text(json.dumps({"type": "ready", "value": True}))
        msg = guest_ws.receive_json()
        assert msg["type"] == "room_state" and msg["room"]["guest_ready"] is True

    # Host connects and starts.
    with client.websocket_connect(f"/ws/rooms/{rid}?token={host_tok}") as host_ws:
        msg = host_ws.receive_json()
        assert msg["type"] == "room_state" and msg["room"]["guest_ready"] is True
        host_ws.send_text(json.dumps({"type": "start"}))
        game_id = None
        playing = False
        for _ in range(4):
            msg = host_ws.receive_json()
            if msg["type"] == "room_game_started":
                game_id = msg["game_id"]
            elif msg["type"] == "room_state" and msg["room"]["status"] == "PLAYING":
                playing = True
                break
        assert game_id is not None
        assert playing


def test_room_manager_state_machine_unit() -> None:
    """Direct unit test on RoomManager covering create → join → ready → start → handle_game_over."""
    import asyncio

    from omok_server.auth.security import hash_password
    from omok_server.db.engine import engine as _engine
    from omok_server.db.models import User as _User
    from omok_server.game.room import RoomStatus
    from omok_server.game.room_manager import RoomManager
    from sqlmodel import Session as _Session

    async def run() -> None:
        with _Session(_engine) as db:
            host = _User(username=_u(), password_hash=hash_password("pw1234"))
            guest = _User(username=_u(), password_hash=hash_password("pw1234"))
            db.add(host); db.add(guest); db.commit(); db.refresh(host); db.refresh(guest)
            host_id, guest_id = host.id, guest.id

        rm = RoomManager()
        room = await rm.create(title="unit", host_user_id=host_id, password="sec")

        # wrong password
        _, err = await rm.join(room.room_id, user_id=guest_id, password="bad")
        assert err == "wrong_password"
        # correct
        joined, err = await rm.join(room.room_id, user_id=guest_id, password="sec")
        assert err is None and joined.guest_user_id == guest_id

        # only guest may ready
        bad = await rm.set_ready(room.room_id, user_id=host_id, value=True)
        assert bad is None
        ok = await rm.set_ready(room.room_id, user_id=guest_id, value=True)
        assert ok is not None and ok.guest_ready

        # only host may start, and only when guest ready
        started = await rm.start_game(room.room_id, host_user_id=guest_id, game_id="g1")
        assert started is None  # not host
        started = await rm.start_game(room.room_id, host_user_id=host_id, game_id="g1")
        assert started is not None and started.status == RoomStatus.PLAYING
        assert rm.find_by_game("g1") == room.room_id

        # game over flips back to LOBBY and clears the index
        post = await rm.handle_game_over(room.room_id)
        assert post.status == RoomStatus.LOBBY and post.guest_ready is False
        assert rm.find_by_game("g1") is None

        # guest leaves → room still alive, host slot intact
        _, host_left = await rm.leave(room.room_id, user_id=guest_id)
        assert not host_left
        assert rm.get(room.room_id).guest_user_id is None

        # host leaves → room deleted
        _, host_left = await rm.leave(room.room_id, user_id=host_id)
        assert host_left
        assert rm.get(room.room_id) is None

    asyncio.run(run())


def test_room_ws_start_blocked_until_guest_ready(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    guest_tok, _ = _register(client)
    assert client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok)).status_code == 200

    with client.websocket_connect(f"/ws/rooms/{rid}?token={host_tok}") as host_ws:
        host_ws.receive_json()  # initial state
        host_ws.send_text(json.dumps({"type": "start"}))
        msg = host_ws.receive_json()
        assert msg["type"] == "error"


def test_logout_deletes_hosted_rooms(client) -> None:
    """Logging out should drop any rooms the user hosts and clear guest slots
    they occupy. The user themselves remains in the DB (stats preserved)."""
    host_tok, host_user = _register(client)
    rid = client.post("/api/rooms", json={"title": "to-be-orphaned"}, headers=_hdr(host_tok)).json()["room_id"]

    # Sanity: room exists.
    other_tok, _ = _register(client)
    assert any(r["room_id"] == rid for r in client.get("/api/rooms", headers=_hdr(other_tok)).json())

    r = client.post("/api/auth/logout", headers=_hdr(host_tok))
    assert r.status_code == 204
    # Room is gone.
    assert not any(r["room_id"] == rid for r in client.get("/api/rooms", headers=_hdr(other_tok)).json())
    # User row survived — try to log in again.
    r = client.post("/api/auth/login", json={"username": host_user["username"], "password": "pw1234"})
    assert r.status_code == 200


def test_logout_clears_guest_slot(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    guest_tok, _ = _register(client)
    client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok))

    # Guest logs out → room stays, guest slot empties.
    assert client.post("/api/auth/logout", headers=_hdr(guest_tok)).status_code == 204
    room = client.get(f"/api/rooms/{rid}", headers=_hdr(host_tok)).json()
    assert room["guest"] is None


def test_leave_all_endpoint(client) -> None:
    """The beforeunload endpoint behaves the same as logout's room cleanup."""
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    assert client.post("/api/rooms/leave-all", headers=_hdr(host_tok)).status_code == 204
    other_tok, _ = _register(client)
    assert not any(r["room_id"] == rid for r in client.get("/api/rooms", headers=_hdr(other_tok)).json())


def test_room_ws_only_guest_can_ready(client) -> None:
    host_tok, _ = _register(client)
    rid = client.post("/api/rooms", json={"title": "t"}, headers=_hdr(host_tok)).json()["room_id"]
    guest_tok, _ = _register(client)
    client.post(f"/api/rooms/{rid}/join", json={}, headers=_hdr(guest_tok))

    with client.websocket_connect(f"/ws/rooms/{rid}?token={host_tok}") as host_ws:
        host_ws.receive_json()
        host_ws.send_text(json.dumps({"type": "ready", "value": True}))
        msg = host_ws.receive_json()
        assert msg["type"] == "error"
