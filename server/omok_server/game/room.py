"""Room model: a lobby waiting room for one HVH game.

Volatile / in-memory only — wiped on server restart. Per Phase 3 plan, this
trade-off is acceptable for local dev; Match (persistent stats) lives in
SQLite so completed games survive even when their hosting room doesn't.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class RoomStatus(str, Enum):
    LOBBY = "LOBBY"
    PLAYING = "PLAYING"


@dataclass
class Room:
    room_id: str
    title: str
    host_user_id: int
    password_hash: str | None = None  # None = public room
    guest_user_id: int | None = None
    status: RoomStatus = RoomStatus.LOBBY
    current_game_id: str | None = None
    guest_ready: bool = False
    games_played: int = 0  # incremented on each completed game; drives the "한 판 더" CTA
    created_at: float = field(default_factory=time.time)
    # Asyncio lock guarding mutations. NEVER acquire `room.lock` while holding
    # a GameSession lock — order is always game.lock → room.lock (see plan §9.3).
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @staticmethod
    def new(*, title: str, host_user_id: int, password_hash: str | None = None) -> "Room":
        return Room(
            room_id=uuid.uuid4().hex[:8],
            title=title,
            host_user_id=host_user_id,
            password_hash=password_hash,
        )

    def is_member(self, user_id: int) -> bool:
        return user_id == self.host_user_id or user_id == self.guest_user_id

    def is_full(self) -> bool:
        return self.guest_user_id is not None

    def can_start(self) -> bool:
        return (
            self.status == RoomStatus.LOBBY
            and self.guest_user_id is not None
            and self.guest_ready
        )
