"""Shared chat helpers used by /ws/lobby, /ws/rooms, /ws/games.

Each channel keeps a fixed-size rolling buffer so a freshly connected client
sees recent context. On `chat` from a client we validate, append, and
broadcast to everyone on the same bus. Rate limiting is per (channel, user).
"""
from __future__ import annotations

import time
from collections import deque
from enum import Enum
from typing import Awaitable, Callable

from omok_server.db.models import User
from omok_server.schemas import SChatHistoryMsg, SChatMsg

CHAT_BUFFER_SIZE = 50
MAX_MESSAGE_LEN = 200

# Rate limit: a user may send up to RATE_LIMIT messages per RATE_WINDOW_S
# seconds on any one channel. Per-(channel, user_id) bucket.
RATE_LIMIT = 10
RATE_WINDOW_S = 10.0

# Channel-keyed buffers. Lobby uses a single global buffer keyed by the
# sentinel "lobby"; room/game channels use their respective id.
_buffers: dict[str, deque[dict]] = {}

# (channel_key, user_id) -> recent send timestamps (sliding window).
_rate_state: dict[tuple[str, int], list[float]] = {}


class ChatResult(Enum):
    OK = "ok"
    EMPTY = "empty"          # whitespace-only message, silently dropped
    RATE_LIMITED = "rate"    # too many messages too fast


def _key_buffer(key: str) -> deque[dict]:
    buf = _buffers.get(key)
    if buf is None:
        buf = deque(maxlen=CHAT_BUFFER_SIZE)
        _buffers[key] = buf
    return buf


def history_for(key: str) -> SChatHistoryMsg | None:
    """Build the SChatHistoryMsg payload for a new connection. Returns None
    (rather than an empty SChatHistoryMsg) when the buffer is empty — this
    keeps the WS stream silent for fresh channels so existing tests that
    don't care about chat history don't have to drain it."""
    buf = _key_buffer(key)
    if not buf:
        return None
    msgs = [SChatMsg.model_validate(m) for m in buf]
    return SChatHistoryMsg(messages=msgs)


def clear_buffer(key: str) -> None:
    """Test-only helper — wipe a channel's chat history."""
    _buffers.pop(key, None)


def clear_all_buffers() -> None:
    """Test-only helper."""
    _buffers.clear()
    _rate_state.clear()


def drop_channel(key: str) -> None:
    """Forget a channel's buffer entirely (e.g., room deleted)."""
    _buffers.pop(key, None)
    # Drop per-channel rate state too — it's tied to the channel's lifetime.
    for k in [k for k in _rate_state if k[0] == key]:
        _rate_state.pop(k, None)


def _check_rate(key: str, user_id: int, *, now: float | None = None) -> bool:
    """True if this user is within the rate budget for this channel."""
    if now is None:
        now = time.time()
    bucket_key = (key, user_id)
    bucket = _rate_state.setdefault(bucket_key, [])
    # Drop timestamps outside the window.
    cutoff = now - RATE_WINDOW_S
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    return True


async def handle_incoming_chat(
    *,
    key: str,
    user: User,
    text: str,
    broadcast: Callable[[dict], Awaitable[None]],
    role: str = "player",
) -> ChatResult:
    """Validate, append, and broadcast. Returns the outcome so callers can
    decide whether to notify the offender (e.g., RATE_LIMITED → send error
    back to just the sender's socket).

    `role` is "player" for lobby/room/game participants and "spectator" for
    live game viewers — the frontend uses it to render a "[관전]" prefix."""
    text = (text or "").strip()
    if not text:
        return ChatResult.EMPTY
    if len(text) > MAX_MESSAGE_LEN:
        text = text[:MAX_MESSAGE_LEN]

    if not _check_rate(key, user.id):
        return ChatResult.RATE_LIMITED

    payload = SChatMsg(
        user_id=user.id,
        username=user.username,
        text=text,
        server_time_ms=int(time.time() * 1000),
        role=role,
    ).model_dump()

    _key_buffer(key).append(payload)
    await broadcast(payload)
    return ChatResult.OK


async def emit_system_message(
    *,
    key: str,
    text: str,
    broadcast: Callable[[dict], Awaitable[None]],
) -> None:
    """Server-originated message (e.g., "alice 입장"). user_id=0, username="시스템",
    is_system=True so the client renders it distinctly. Bypasses rate limiting."""
    payload = SChatMsg(
        user_id=0,
        username="시스템",
        text=text,
        server_time_ms=int(time.time() * 1000),
        is_system=True,
    ).model_dump()
    _key_buffer(key).append(payload)
    await broadcast(payload)
