"""Singleton in-memory registry of active Rooms.

Mirrors the existing `manager` (GameSession registry) pattern. Broadcast hooks
(lobby/room WS) are registered at startup so room state changes can push to
connected clients without circular imports between game/* and api/*.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable

from omok_server.auth.security import hash_password, verify_password
from omok_server.game.room import Room, RoomStatus


# Broadcast hook signatures. Concrete impls live in api/ws_lobby.py and
# api/ws_rooms.py and are installed at app startup via main.py to avoid
# importing FastAPI websocket code from game/.
LobbyBroadcast = Callable[[dict], Awaitable[None]]
RoomBroadcast = Callable[[str, dict], Awaitable[None]]


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()
        # Reverse index: game_id → room_id. Lets us find which room hosts a
        # given GameSession without scanning every room when the game ends.
        self._game_to_room: dict[str, str] = {}
        # Hook setters; default no-ops until main.py installs the real ones.
        self.broadcast_lobby: LobbyBroadcast = self._noop_lobby
        self.broadcast_room: RoomBroadcast = self._noop_room

    @staticmethod
    async def _noop_lobby(_payload: dict) -> None: ...
    @staticmethod
    async def _noop_room(_room_id: str, _payload: dict) -> None: ...

    # ----- queries -----

    def get(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def list(self) -> Iterable[Room]:
        return list(self._rooms.values())

    def find_by_game(self, game_id: str) -> str | None:
        return self._game_to_room.get(game_id)

    # ----- mutations -----

    async def create(self, *, title: str, host_user_id: int, password: str | None) -> Room:
        pw_hash = hash_password(password) if password else None
        room = Room.new(title=title, host_user_id=host_user_id, password_hash=pw_hash)
        async with self._lock:
            self._rooms[room.room_id] = room
        return room

    async def remove(self, room_id: str) -> None:
        async with self._lock:
            room = self._rooms.pop(room_id, None)
            if room is not None and room.current_game_id is not None:
                self._game_to_room.pop(room.current_game_id, None)

    async def join(self, room_id: str, *, user_id: int, password: str | None) -> tuple[Room | None, str | None]:
        """Returns (room, error_code). error_code is one of:
            "not_found", "full", "wrong_password", "already_in", "in_progress".
        On success, returns (room, None).
        """
        room = self._rooms.get(room_id)
        if room is None:
            return None, "not_found"
        async with room.lock:
            if room.status != RoomStatus.LOBBY:
                return room, "in_progress"
            if room.host_user_id == user_id:
                return room, "already_in"
            if room.guest_user_id == user_id:
                return room, None  # idempotent re-join
            if room.is_full():
                return room, "full"
            if room.password_hash is not None:
                if not password or not verify_password(password, room.password_hash):
                    return room, "wrong_password"
            room.guest_user_id = user_id
            room.guest_ready = False
        return room, None

    async def leave(self, room_id: str, *, user_id: int) -> tuple[Room | None, bool]:
        """Returns (room_or_None, host_left_so_deleted)."""
        room = self._rooms.get(room_id)
        if room is None:
            return None, False
        async with room.lock:
            if user_id == room.host_user_id:
                # Host leaving → close room.
                pass
            elif user_id == room.guest_user_id:
                room.guest_user_id = None
                room.guest_ready = False
                return room, False
            else:
                # Non-member trying to leave: no-op.
                return room, False
        # Host left. Delete the room (outside the room.lock to avoid nesting).
        await self.remove(room_id)
        return None, True

    async def set_ready(self, room_id: str, *, user_id: int, value: bool) -> Room | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        async with room.lock:
            if user_id != room.guest_user_id:
                return None
            if room.status != RoomStatus.LOBBY:
                return None
            room.guest_ready = value
        return room

    async def start_game(self, room_id: str, *, host_user_id: int, game_id: str) -> Room | None:
        """Transition room LOBBY → PLAYING and remember the game_id mapping.
        Returns the updated room, or None if not allowed."""
        room = self._rooms.get(room_id)
        if room is None:
            return None
        async with room.lock:
            if host_user_id != room.host_user_id:
                return None
            if not room.can_start():
                return None
            room.status = RoomStatus.PLAYING
            room.current_game_id = game_id
        # Index outside the room.lock; only the manager lock guards this dict.
        async with self._lock:
            self._game_to_room[game_id] = room_id
        return room

    async def handle_game_over(self, room_id: str) -> Room | None:
        """Transition PLAYING → LOBBY after the game ends. Idempotent."""
        room = self._rooms.get(room_id)
        if room is None:
            return None
        async with room.lock:
            game_id = room.current_game_id
            room.status = RoomStatus.LOBBY
            room.current_game_id = None
            room.guest_ready = False
        if game_id is not None:
            async with self._lock:
                self._game_to_room.pop(game_id, None)
        return room


room_manager = RoomManager()
