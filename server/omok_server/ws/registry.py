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
# Fired only on a true offline↔online transition (first socket appears / last
# socket disappears), with (user_id, online). Distinct from PresenceListener,
# which fires on every connect/disconnect; session listeners must see each user
# go online and offline exactly once per session so they can be paired into a
# duration.
SessionListener = Callable[[int, bool], Awaitable[None]]


class WsRegistry:
    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        # Notified when a user goes from offline → online or online → offline
        # (not on every additional tab they open). Subscribers do their own
        # broadcasting; we only signal "presence set changed".
        self._presence_listeners: list[PresenceListener] = []
        self._session_listeners: list[SessionListener] = []
        # Strong refs to in-flight listener tasks. `asyncio.create_task` only
        # keeps weak refs in the event loop, so a task whose handle we drop
        # can be garbage-collected mid-execution (Python 3.11+ docs warn
        # about this). We hold strong refs here and clear them on completion.
        # Observed in the wild: lobby reconnect after a back-navigation lost
        # its presence broadcast because the create_task was GC'd before
        # the broadcast ran.
        self._pending_tasks: set[asyncio.Task] = set()

    async def register(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            # Empty set (incl. a freshly-defaulted one) → this is the user's
            # first live socket, i.e. an offline→online transition.
            became_online = len(self._by_user[user_id]) == 0
            self._by_user[user_id].add(ws)
        if became_online:
            self._notify_session(user_id, online=True)
        # Always notify — a "transition only" check (was offline → now online)
        # silently loses presence frames under reconnect races: when an old
        # socket hasn't been removed yet, the new socket's register call sees
        # the user as still online and skips the broadcast. Notifying on
        # every connect costs an extra small payload per duplicate tab but
        # makes the panel reliably reflect reality.
        await self._notify_presence()

    async def unregister(self, user_id: int, ws: WebSocket) -> None:
        became_offline = False
        async with self._lock:
            sockets = self._by_user.get(user_id)
            if sockets is None:
                return
            sockets.discard(ws)
            if not sockets:
                self._by_user.pop(user_id, None)
                became_offline = True
        if became_offline:
            self._notify_session(user_id, online=False)
        # Same reasoning as register: notify unconditionally so a reconnect
        # race can't drop the "user is gone" frame either.
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

    def add_session_listener(self, cb: SessionListener) -> None:
        """Register a coroutine fired on each offline↔online transition with
        (user_id, online). Used to log connect/disconnect for usage analytics.
        Scheduled fire-and-forget, same as presence (see `_notify_session`)."""
        self._session_listeners.append(cb)

    def _notify_session(self, user_id: int, *, online: bool) -> None:
        # Fire-and-forget for the same reason as `_notify_presence`: this runs
        # inside the WS handler's `finally` mid close-handshake, where awaiting
        # could deadlock. Strong refs held in `_pending_tasks`.
        for cb in list(self._session_listeners):
            try:
                task = asyncio.create_task(cb(user_id, online))
            except Exception:
                continue
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

    async def _notify_presence(self) -> None:
        # Fire-and-forget: the caller is often the WS handler's `finally`,
        # running mid close-handshake. Awaiting the listener there can
        # deadlock against the close ack (TestClient and real browser
        # clients alike), so we schedule the listener on the event loop
        # and let it run after the handler exits.
        #
        # NB: keep a strong reference to each task in `_pending_tasks`.
        # `asyncio.create_task` returns a Task the loop only weakly
        # references; without a strong ref the GC can collect it mid-run.
        # `add_done_callback` cleans up after completion.
        for cb in list(self._presence_listeners):
            try:
                task = asyncio.create_task(cb())
            except Exception:
                continue
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)


registry = WsRegistry()
