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
    DRAW = "DRAW"


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
    user_id: int | None = None  # NULL for AI (or pre-Phase-3A sessions)
    wins: int | None = None     # populated by session.to_state_msg via DB lookup
    losses: int | None = None
    draws: int | None = None


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


# ---------- Auth (Phase 3A) ----------


class UserSummary(BaseModel):
    id: int
    username: str
    wins: int
    losses: int
    # Draws are shown in 전적 alongside wins/losses but deliberately excluded
    # from win-rate math (denominator = wins + losses). Defaults to 0 so
    # older clients that don't send this field still serialize fine.
    draws: int = 0
    current_room_id: str | None = None  # set on /api/auth/me when the user sits in a room

    @property
    def games_played(self) -> int:
        # Decided count for win-rate purposes — draws excluded by design.
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return 0.0 if self.games_played == 0 else self.wins / self.games_played


class MatchSummary(BaseModel):
    """One row of a user's recent match history for the hover card."""
    match_id: int
    opponent_username: str | None  # None for AI games
    opponent_user_id: int | None
    your_color: ColorStr
    you_won: bool
    # True when the match ended in a draw (board filled with no winner).
    # The client should prefer this over `you_won` when deciding what label
    # to render — a draw is neither a win nor a loss.
    is_draw: bool = False
    over_reason: GameOverReason
    is_ai_game: bool
    ended_at: float  # unix timestamp (seconds)
    move_count: int


class MatchDetail(BaseModel):
    """Full match payload for the replay viewer."""
    match_id: int
    game_id: str
    black_username: str | None
    white_username: str | None
    winner_color: ColorStr | None  # None when AI won (no human winner_user_id)
    over_reason: GameOverReason
    is_ai_game: bool
    started_at: float
    ended_at: float
    move_count: int
    moves: list[Stone]  # in play order, alternating BLACK/WHITE


class RecentMatches(BaseModel):
    user_id: int
    matches: list[MatchSummary]


class LeaderboardEntry(BaseModel):
    """One row of the global ranking. Sorted client→server by wins desc."""
    rank: int
    user_id: int
    username: str
    wins: int
    losses: int
    draws: int = 0


class Leaderboard(BaseModel):
    entries: list[LeaderboardEntry]


class AuthCredentials(BaseModel):
    username: str = Field(min_length=2, max_length=24)
    password: str = Field(min_length=4, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserSummary


# Optional realtime nudge: server can include this alongside SGameOverMsg so
# clients refresh their cached wins/losses without an extra REST call.
class StatsUpdate(BaseModel):
    user_id: int
    wins: int
    losses: int
    draws: int = 0


# ---------- Rooms (Phase 3B) ----------


class RoomStatusStr(str, Enum):
    LOBBY = "LOBBY"
    PLAYING = "PLAYING"


class RoomMemberSummary(BaseModel):
    """Summary of one user as seen from inside a room (host or guest slot)."""
    user_id: int
    username: str
    wins: int
    losses: int
    draws: int = 0


class RoomSummary(BaseModel):
    """Compact list-view row used by the lobby."""
    room_id: str
    title: str
    has_password: bool
    host: RoomMemberSummary
    guest: RoomMemberSummary | None
    status: RoomStatusStr
    created_at: float


class RoomDetail(RoomSummary):
    """Room state from inside the room (members + readiness)."""
    guest_ready: bool
    current_game_id: str | None = None
    games_played: int = 0  # drives "한 판 더" CTA on rematch


class CreateRoomReq(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    password: str | None = Field(default=None, max_length=64)


class JoinRoomReq(BaseModel):
    password: str | None = Field(default=None, max_length=64)


# ----- Room WS messages -----


class CRoomReadyMsg(BaseModel):
    type: Literal["ready"] = "ready"
    value: bool


class CRoomStartMsg(BaseModel):
    type: Literal["start"] = "start"


class CRoomLeaveMsg(BaseModel):
    type: Literal["leave"] = "leave"


class SRoomStateMsg(BaseModel):
    type: Literal["room_state"] = "room_state"
    room: RoomDetail


class SRoomGameStartedMsg(BaseModel):
    type: Literal["room_game_started"] = "room_game_started"
    game_id: str


class SRoomClosedMsg(BaseModel):
    type: Literal["room_closed"] = "room_closed"
    reason: Literal["host_left", "kicked"] = "host_left"


# ----- Lobby WS messages -----


class SLobbySnapshotMsg(BaseModel):
    type: Literal["lobby_snapshot"] = "lobby_snapshot"
    rooms: list[RoomSummary]


class SLobbyUpdateMsg(BaseModel):
    type: Literal["lobby_update"] = "lobby_update"
    action: Literal["created", "updated", "removed"]
    room_id: str
    room: RoomSummary | None = None  # null when action == "removed"


# ----- Chat (shared by lobby / room / game channels) -----


class CChatMsg(BaseModel):
    type: Literal["chat"] = "chat"
    text: str = Field(min_length=1, max_length=200)


class SChatMsg(BaseModel):
    type: Literal["chat"] = "chat"
    user_id: int                     # 0 reserved for system messages
    username: str                    # "시스템" for system messages
    text: str
    server_time_ms: int
    is_system: bool = False          # True → rendered differently by the client


class SChatHistoryMsg(BaseModel):
    """Sent once to a freshly connected client so they can see recent
    conversation. Subsequent live messages arrive as individual SChatMsg."""
    type: Literal["chat_history"] = "chat_history"
    messages: list[SChatMsg]


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
    stats_updates: list[StatsUpdate] = Field(default_factory=list)
    back_to_room: str | None = None  # populated in Phase 3B if the game was room-hosted
    match_id: int | None = None  # DB Match row id — frontend uses this to deep-link the replay


class SErrorMsg(BaseModel):
    type: Literal["error"] = "error"
    message: str


class SPongMsg(BaseModel):
    type: Literal["pong"] = "pong"
