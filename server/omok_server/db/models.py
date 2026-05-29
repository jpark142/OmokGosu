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
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
