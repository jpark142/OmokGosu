"""Per-user WebSocket registry for cross-channel force-close.

Single-session login (commit dff48d0) bumps `User.token_version` so subsequent
REST/WS auth checks reject the old token. That left a gap: WS connections
already accepted with the old token kept running until their next inbound
message. This registry closes that gap — on login we look up every socket the
user currently owns (across lobby / room / game channels) and close them with
code 4401.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class WsRegistry:
    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def register(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_user[user_id].add(ws)

    async def unregister(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            sockets = self._by_user.get(user_id)
            if sockets is None:
                return
            sockets.discard(ws)
            if not sockets:
                self._by_user.pop(user_id, None)

    async def close_all(self, user_id: int, *, code: int = 4401) -> int:
        """Close every socket owned by `user_id`. Returns number of sockets closed."""
        async with self._lock:
            sockets = list(self._by_user.get(user_id, ()))
        for ws in sockets:
            try:
                await ws.close(code=code)
            except Exception:
                pass
        return len(sockets)


registry = WsRegistry()
