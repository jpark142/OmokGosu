"""Per-user WebSocket registry: tracks which users own which sockets so we
can (a) force-close stale sessions on a new login, and (b) compute the live
"who's online" set used by the lobby presence panel.

Single-session login (commit dff48d0) bumps `User.token_version` so subsequent
REST/WS auth checks reject the old token. That left a gap: WS connections
already accepted with the old token kept running until their next inbound
message. This registry closes that gap — on login we look up every socket the
user currently owns (across lobby / room / game channels) and close them with
code 4401.

The presence-listener hook fires whenever a user transitions empty↔non-empty
(first socket appears / last socket disappears), so subscribers can broadcast
an updated online-users list without polling.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import WebSocket


PresenceListener = Callable[[], Awaitable[None]]


class WsRegistry:
    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        # Notified when a user goes from offline → online or online → offline
        # (not on every additional tab they open). Subscribers do their own
        # broadcasting; we only signal "presence set changed".
        self._presence_listeners: list[PresenceListener] = []

    async def register(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            became_online = user_id not in self._by_user or not self._by_user[user_id]
            self._by_user[user_id].add(ws)
        if became_online:
            await self._notify_presence()

    async def unregister(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            sockets = self._by_user.get(user_id)
            if sockets is None:
                return
            sockets.discard(ws)
            went_offline = not sockets
            if went_offline:
                self._by_user.pop(user_id, None)
        if went_offline:
            await self._notify_presence()

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

    def online_user_ids(self) -> set[int]:
        """Snapshot of user_ids that currently own at least one open socket."""
        return set(self._by_user.keys())

    def add_presence_listener(self, cb: PresenceListener) -> None:
        """Register a coroutine to be awaited each time the online set changes.

        Listeners run sequentially and exceptions are swallowed so one bad
        subscriber can't take down the others or the calling WS handler.
        """
        self._presence_listeners.append(cb)

    async def _notify_presence(self) -> None:
        # Fire-and-forget: the caller is often the WS handler's `finally`,
        # running mid close-handshake. Awaiting the listener there can
        # deadlock against the close ack (TestClient and real browser
        # clients alike), so we schedule the listener on the event loop
        # and let it run after the handler exits.
        for cb in list(self._presence_listeners):
            try:
                asyncio.create_task(cb())
            except Exception:
                pass


registry = WsRegistry()
