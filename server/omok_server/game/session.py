"""GameSession: state machine for one game.

Tracks: engine state, clock, players (color → name/kind), termination status.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from omok_server.game.clock import GameClock, now_monotonic_ms
from omok_server.game.engine import Engine
from omok_server.schemas import (
    ClocksSnapshot,
    ColorStr,
    ForbiddenReason,
    GameMode,
    GameOverReason,
    GameStatus,
    PlayerInfo,
    PlayerKind,
    SStateMsg,
    Stone,
)


@dataclass
class GameSession:
    game_id: str
    mode: GameMode
    engine: Engine = field(default_factory=Engine)
    clock: GameClock = field(default_factory=GameClock)
    players: dict[ColorStr, PlayerInfo] = field(default_factory=dict)
    status: GameStatus = GameStatus.IN_PROGRESS
    over_reason: GameOverReason | None = None
    winner: ColorStr | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    started_at: datetime = field(default_factory=datetime.utcnow)
    recorded_match: bool = False  # set True after services.stats.record_match runs

    @staticmethod
    def new(
        mode: GameMode = GameMode.HVH,
        human_name: str = "Player",
        ai_name: str | None = None,
        human_user_id: int | None = None,
        guest_name: str | None = None,
        guest_user_id: int | None = None,
    ) -> "GameSession":
        """Create a new session.

        - HVH (방 → 게임): pass both `human_*` (host) and `guest_*` (guest).
        - HVA (Home → 게임): pass `human_*` only; AI fills the other slot.

        Backwards-compatible: legacy callers that omit the new fields still
        produce a valid session, but with `user_id=None` everywhere — stats
        won't record. New code should pass user IDs.
        """
        gid = uuid.uuid4().hex[:12]
        gs = GameSession(game_id=gid, mode=mode)
        human_color = random.choice([ColorStr.BLACK, ColorStr.WHITE])
        opp_color = ColorStr.WHITE if human_color == ColorStr.BLACK else ColorStr.BLACK
        if mode == GameMode.HVH:
            gs.players = {
                human_color: PlayerInfo(
                    name=human_name, kind=PlayerKind.HUMAN, user_id=human_user_id
                ),
                opp_color: PlayerInfo(
                    name=guest_name or "Player 2",
                    kind=PlayerKind.HUMAN,
                    user_id=guest_user_id,
                ),
            }
        else:
            gs.players = {
                human_color: PlayerInfo(
                    name=human_name, kind=PlayerKind.HUMAN, user_id=human_user_id
                ),
                opp_color: PlayerInfo(
                    name=ai_name or "AI", kind=PlayerKind.AI, user_id=None
                ),
            }
        gs.clock.start_turn(ColorStr.BLACK)
        return gs

    # ----- queries -----

    def your_color(self) -> ColorStr:
        """For HVA mode, returns the human's color. For HVH, returns BLACK by default."""
        for color, info in self.players.items():
            if info.kind == PlayerKind.HUMAN:
                return color
        return ColorStr.BLACK

    def get_ai_for(self, color: ColorStr):
        """Return a fresh AI instance if `color` is an AI player on this session, else None.

        Dispatches by the level stored in `players[color].name`. The level
        string is either an `AILevel` value ("random"/"smart"/"minimax") or a
        difficulty-suffixed "minimax:easy" / "minimax:hard" form.
        """
        info = self.players.get(color)
        if info is None or info.kind != PlayerKind.AI:
            return None
        level = (info.name or "").lower()
        if level == "random":
            from omok_server.ai.random_ai import RandomAI
            return RandomAI()
        if level.startswith("minimax"):
            from omok_server.ai.minimax_ai import MinimaxAI
            suffix = level.split(":", 1)[1] if ":" in level else None
            return MinimaxAI(difficulty=suffix)
        from omok_server.ai.smart_ai import SmartAI
        return SmartAI()

    def is_over(self) -> bool:
        return self.status == GameStatus.OVER

    def to_state_msg(self) -> SStateMsg:
        # Hydrate player stats from DB on each snapshot. Cheap: at most 2 rows.
        # Lazy import to avoid circular dependency (services.stats imports GameSession).
        from omok_server.services.stats import fetch_user_stats

        user_ids = [info.user_id for info in self.players.values() if info.user_id is not None]
        stats_map = fetch_user_stats(user_ids) if user_ids else {}

        hydrated: dict[ColorStr, PlayerInfo] = {}
        for color, info in self.players.items():
            wins_losses = stats_map.get(info.user_id) if info.user_id is not None else None
            if wins_losses is not None:
                hydrated[color] = info.model_copy(
                    update={"wins": wins_losses[0], "losses": wins_losses[1]}
                )
            else:
                hydrated[color] = info

        return SStateMsg(
            game_id=self.game_id,
            stones=self.engine.stones(),
            to_move=self.engine.side_to_move,
            move_number=self.engine.move_number,
            last_move=self.engine.last_move(),
            forbidden_squares=self.engine.forbidden_squares()
            if (self.engine.side_to_move == ColorStr.BLACK and not self.is_over())
            else [],
            clocks=ClocksSnapshot(
                black=self.clock.live_snapshot_for(ColorStr.BLACK),
                white=self.clock.live_snapshot_for(ColorStr.WHITE),
            ),
            players=hydrated,
            status=self.status,
            server_time_ms=int(time.time() * 1000),
        )

    # ----- mutations -----

    def apply_move(self, r: int, c: int, color: ColorStr) -> ForbiddenReason | None:
        """Validate + play. Returns reason if rejected. On success, returns None and
        the clock is rotated to the opponent. If the move ends the game, status is
        updated to OVER with the appropriate reason."""
        if self.is_over():
            return ForbiddenReason.GAME_OVER
        reason = self.engine.validate(r, c, color)
        if reason is not None:
            return reason

        self.engine.play(r, c, color)
        # Consume the time used by `color`'s turn and stop the clock.
        self.clock.apply_move()

        # Check terminal conditions.
        if self.engine.last_move_wins():
            self.status = GameStatus.OVER
            self.winner = color
            self.over_reason = (
                GameOverReason.OVERLINE_WIN
                if color == ColorStr.WHITE and self._last_move_was_overline()
                else GameOverReason.FIVE
            )
            return None

        # Continue: start opponent's clock.
        opp = ColorStr.WHITE if color == ColorStr.BLACK else ColorStr.BLACK
        self.clock.start_turn(opp)
        return None

    def resign(self, color: ColorStr) -> None:
        if self.is_over():
            return
        self.status = GameStatus.OVER
        self.winner = ColorStr.WHITE if color == ColorStr.BLACK else ColorStr.BLACK
        self.over_reason = GameOverReason.RESIGN

    def force_timeout(self, color: ColorStr) -> None:
        if self.is_over():
            return
        self.status = GameStatus.OVER
        self.winner = ColorStr.WHITE if color == ColorStr.BLACK else ColorStr.BLACK
        self.over_reason = GameOverReason.TIMEOUT

    def check_timeout(self) -> ColorStr | None:
        if self.is_over():
            return None
        timed_out = self.clock.check_timeout()
        if timed_out is not None:
            self.force_timeout(timed_out)
        return timed_out

    # ----- internal -----

    def _last_move_was_overline(self) -> bool:
        # Count from last move: if any direction has 6+ in row, it's overline.
        # We don't expose this from C++ directly yet; just inspect history.
        history = self.engine.board.history()
        if not history:
            return False
        last_r, last_c, _color = history[-1]
        cells_flat = self.engine.board.cells()
        BOARD = 15

        def at(r: int, c: int) -> int:
            if r < 0 or r >= BOARD or c < 0 or c >= BOARD:
                return 0
            return cells_flat[r * BOARD + c]

        last_color = at(last_r, last_c)
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            run = 1
            k = 1
            while at(last_r + dr * k, last_c + dc * k) == last_color:
                run += 1
                k += 1
            k = 1
            while at(last_r - dr * k, last_c - dc * k) == last_color:
                run += 1
                k += 1
            if run >= 6:
                return True
        return False
