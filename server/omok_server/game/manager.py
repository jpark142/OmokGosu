"""In-memory game registry.

For Phase 1 we run a single process and hold sessions in a dict. When we
introduce server hosting later, this is the natural seam to swap for a
Redis/Postgres-backed store.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from omok_server.game.session import GameSession


@dataclass
class GameManager:
    sessions: dict[str, GameSession] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add(self, session: GameSession) -> None:
        async with self._lock:
            self.sessions[session.game_id] = session

    def get(self, game_id: str) -> GameSession | None:
        return self.sessions.get(game_id)

    async def remove(self, game_id: str) -> None:
        async with self._lock:
            self.sessions.pop(game_id, None)


# Module-level singleton — wired in main.py.
manager = GameManager()
