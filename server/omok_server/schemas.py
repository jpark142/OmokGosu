"""Pydantic models mirroring the WS/REST wire formats.

These types are the single source of truth for the protocol; the frontend
mirrors them in `web/src/types/protocol.ts`.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------- enums ----------


class ColorStr(str, Enum):
    BLACK = "BLACK"
    WHITE = "WHITE"


class GameMode(str, Enum):
    HVH = "hvh"
    HVA = "hva"


class AILevel(str, Enum):
    RANDOM = "random"
    SMART = "smart"
    MINIMAX = "minimax"
    HEURISTIC = "heuristic"
    ALPHAZERO = "alphazero"


class GameStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    OVER = "OVER"


class GameOverReason(str, Enum):
    FIVE = "FIVE"
    OVERLINE_WIN = "OVERLINE_WIN"
    RESIGN = "RESIGN"
    TIMEOUT = "TIMEOUT"


class ForbiddenReason(str, Enum):
    DOUBLE_THREE = "DOUBLE_THREE"
    DOUBLE_FOUR = "DOUBLE_FOUR"
    OVERLINE = "OVERLINE"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    OCCUPIED = "OCCUPIED"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    GAME_OVER = "GAME_OVER"


class PlayerKind(str, Enum):
    HUMAN = "human"
    AI = "ai"


# ---------- subschemas ----------


class Stone(BaseModel):
    r: int
    c: int
    color: ColorStr


class MovePayload(BaseModel):
    r: int
    c: int
    color: ColorStr | None = None


class PlayerInfo(BaseModel):
    name: str
    kind: PlayerKind


class ClockSnapshot(BaseModel):
    main_ms: int
    byoyomi_periods: int
    byoyomi_ms: int
    in_byoyomi: bool


class ClocksSnapshot(BaseModel):
    black: ClockSnapshot
    white: ClockSnapshot


# ---------- REST request/response ----------


class CreateGameRequest(BaseModel):
    mode: GameMode = GameMode.HVH
    ai_level: AILevel | None = None
    ai_difficulty: str | None = None  # "easy" | "medium" | "hard" — only used by Minimax+ AIs
    player_name: str | None = None


class CreateGameResponse(BaseModel):
    game_id: str
    your_color: ColorStr
    ws_url: str


# ---------- WebSocket: client → server ----------


class CMoveMsg(BaseModel):
    type: Literal["move"] = "move"
    r: int
    c: int


class CResignMsg(BaseModel):
    type: Literal["resign"] = "resign"


class CPingMsg(BaseModel):
    type: Literal["ping"] = "ping"


# ---------- WebSocket: server → client ----------


class SStateMsg(BaseModel):
    type: Literal["state"] = "state"
    game_id: str
    board_size: int = 15
    stones: list[Stone]
    to_move: ColorStr
    move_number: int
    last_move: Stone | None = None
    forbidden_squares: list[tuple[int, int]] = Field(default_factory=list)
    clocks: ClocksSnapshot
    players: dict[ColorStr, PlayerInfo]
    status: GameStatus
    server_time_ms: int


class SMoveAppliedMsg(BaseModel):
    type: Literal["move_applied"] = "move_applied"
    move: Stone
    move_number: int
    last_move_at_ms: int


class STimerTickMsg(BaseModel):
    type: Literal["timer_tick"] = "timer_tick"
    clocks: ClocksSnapshot
    to_move: ColorStr
    server_time_ms: int


class SForbiddenRejectedMsg(BaseModel):
    type: Literal["forbidden_move_rejected"] = "forbidden_move_rejected"
    r: int
    c: int
    reason: ForbiddenReason


class SGameOverMsg(BaseModel):
    type: Literal["game_over"] = "game_over"
    winner: ColorStr | None = None  # None for draw (currently unused)
    reason: GameOverReason


class SErrorMsg(BaseModel):
    type: Literal["error"] = "error"
    message: str


class SPongMsg(BaseModel):
    type: Literal["pong"] = "pong"
