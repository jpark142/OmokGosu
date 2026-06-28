"""SQLModel tables: User (account + denormalized stats) and Match (history)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=24)
    password_hash: str
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    # Counted separately from wins/losses so the UI can show "Nm" without
    # polluting either side. Win rate (wins / (wins + losses)) ignores this.
    draws: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Bumped on every successful login. The current JWT carries this as its
    # `ver` claim; auth deps reject tokens whose ver doesn't match. This is
    # how "new login invalidates previous session" is enforced without
    # tracking individual tokens.
    token_version: int = Field(default=0)


class BugReport(SQLModel, table=True):
    """In-app bug report. Captured by the report dialog; mirrored to a
    GitHub Issue when the API call succeeds. The SQLite row is the source
    of truth — `github_issue_number` is null when the API failed and the
    report exists only locally."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # True when the reporter ticked "익명으로 보내기" — Issue body omits
    # username/user_id but we still record them locally for de-spamming /
    # follow-up. Logged-out reporters have user_id=null regardless.
    anonymous: bool = Field(default=False)
    # Server version at the time of the report, so a regression that snuck
    # in on a deploy is easy to spot in the issue stream.
    version: str = Field(max_length=32)
    # Browser context the reporter was looking at.
    url: str = Field(default="", max_length=512)
    user_agent: str = Field(default="", max_length=512)
    description: str = Field(max_length=4000)
    # Set after a successful GitHub Issues API call. Null if the API was
    # unreachable or the token was revoked.
    github_issue_number: Optional[int] = Field(default=None)
    github_issue_url: Optional[str] = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(index=True, max_length=32)
    black_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    white_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    winner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    over_reason: str = Field(max_length=32)
    started_at: datetime
    ended_at: datetime = Field(default_factory=datetime.utcnow)
    move_count: int = 0
    is_ai_game: bool = False
    # JSON-serialized list of {"r":int, "c":int, "color":"BLACK"|"WHITE"} in
    # play order. Populated on game end so the replay viewer can scrub through
    # moves without reconstructing them. Empty string for matches predating
    # this field.
    moves_json: str = Field(default="[]")


class SessionLog(SQLModel, table=True):
    """One online session per row: from a user's first live socket to their
    last. Multiple tabs collapse into a single session because the WsRegistry
    only signals offline↔online transitions, not every socket.

    Powers later usage analytics (DAU/WAU, session length, concurrent peak) —
    none of which can be reconstructed after the fact, so we capture them as
    they happen. `disconnected_at` is NULL while a session is open; sessions
    orphaned by a server restart are closed on the next startup."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    connected_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    disconnected_at: Optional[datetime] = Field(default=None)
