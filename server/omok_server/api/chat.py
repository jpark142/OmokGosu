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
from omok_server.services.chat_filter import should_blur

CHAT_BUFFER_SIZE = 50
MAX_MESSAGE_LEN = 200

# Rate limit: a user may send up to RATE_LIMIT messages per RATE_WINDOW_S
# seconds on any one channel. Per-(channel, user_id) bucket.
RATE_LIMIT = 10
RATE_WINDOW_S = 10.0

# Spam detection (stricter than rate limit). Sending more than SPAM_THRESHOLD
# messages within SPAM_WINDOW_S = clearly hammering the chat. We mute the
# user on that channel for SPAM_MUTE_S seconds and broadcast a system notice
# so other participants don't think their messages were lost.
SPAM_WINDOW_S = 5.0
SPAM_THRESHOLD = 6
SPAM_MUTE_S = 180.0  # 3 minutes

# Channel-keyed buffers. Lobby uses a single global buffer keyed by the
# sentinel "lobby"; room/game channels use their respective id.
_buffers: dict[str, deque[dict]] = {}

# (channel_key, user_id) -> recent send timestamps (sliding window).
_rate_state: dict[tuple[str, int], list[float]] = {}

# (channel_key, user_id) -> unmute_at unix-ts. Channel-scoped so a spammer
# muted in the lobby can still chat in their own room if they calm down.
_mute_state: dict[tuple[str, int], float] = {}


class ChatResult(Enum):
    OK = "ok"
    EMPTY = "empty"          # whitespace-only message, silently dropped
    RATE_LIMITED = "rate"    # too many messages too fast
    MUTED = "muted"          # user is currently in a spam mute on this channel
    SPAM_MUTED = "spam_muted"  # this message tripped the spam detector — caller should not retry


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
    _mute_state.clear()


def drop_channel(key: str) -> None:
    """Forget a channel's buffer entirely (e.g., room deleted)."""
    _buffers.pop(key, None)
    # Drop per-channel rate + mute state too — tied to the channel's lifetime.
    for k in [k for k in _rate_state if k[0] == key]:
        _rate_state.pop(k, None)
    for k in [k for k in _mute_state if k[0] == key]:
        _mute_state.pop(k, None)


def _check_rate(key: str, user_id: int, *, now: float | None = None) -> bool:
    """True if this user is within the rate budget for this channel.

    Side effect on success: records `now` in the user's bucket. Also serves
    as the spam-window probe: callers that want to detect spam should peek
    at the bucket length *before* the append, via `_count_in_window`.
    """
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


def _is_muted(key: str, user_id: int, *, now: float) -> bool:
    """True if this (channel, user) is currently in a mute. Auto-expires."""
    expires = _mute_state.get((key, user_id))
    if expires is None:
        return False
    if expires <= now:
        _mute_state.pop((key, user_id), None)
        return False
    return True


def _detect_and_apply_spam(key: str, user_id: int, *, now: float) -> bool:
    """Return True iff this attempt triggers the spam threshold; mute set.

    Inspects the rate bucket (already updated with this attempt's timestamp)
    and asks: are there ≥ SPAM_THRESHOLD entries within the last
    SPAM_WINDOW_S? If so, register a mute lasting SPAM_MUTE_S.
    """
    bucket = _rate_state.get((key, user_id), [])
    cutoff = now - SPAM_WINDOW_S
    recent = sum(1 for t in bucket if t >= cutoff)
    if recent >= SPAM_THRESHOLD:
        _mute_state[(key, user_id)] = now + SPAM_MUTE_S
        return True
    return False


def mute_remaining_s(key: str, user_id: int, *, now: float | None = None) -> float:
    """How many seconds remain on this user's mute (0 if not muted)."""
    if now is None:
        now = time.time()
    expires = _mute_state.get((key, user_id))
    if expires is None or expires <= now:
        return 0.0
    return expires - now


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
    live game viewers — the frontend uses it to render a "[관전]" prefix.
    """
    text = (text or "").strip()
    if not text:
        return ChatResult.EMPTY
    if len(text) > MAX_MESSAGE_LEN:
        text = text[:MAX_MESSAGE_LEN]

    now = time.time()

    # Active mute? Reject silently except for the OK→error response sent by
    # the caller. We don't broadcast on every blocked attempt so a muted
    # spammer can't keep flooding the channel via the system-message
    # mechanism.
    if _is_muted(key, user.id, now=now):
        return ChatResult.MUTED

    if not _check_rate(key, user.id, now=now):
        return ChatResult.RATE_LIMITED

    # Spam check uses the bucket we just appended to. A burst of 6+ messages
    # within 5s = mute for 3 minutes + system-message announce.
    if _detect_and_apply_spam(key, user.id, now=now):
        await broadcast(
            SChatMsg(
                user_id=0,
                username="시스템",
                text=f"{user.username}님이 도배 감지로 3분간 채팅이 금지되었습니다.",
                server_time_ms=int(now * 1000),
                is_system=True,
            ).model_dump()
        )
        return ChatResult.SPAM_MUTED

    payload = SChatMsg(
        user_id=user.id,
        username=user.username,
        text=text,
        server_time_ms=int(now * 1000),
        role=role,
        is_blurred=should_blur(text),
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
