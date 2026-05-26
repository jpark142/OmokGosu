"""Phase 2 AI: iterative-deepening negamax with alpha-beta + TT (C++).

Thin Python wrapper around `omok_core.Searcher`. The C++ side handles all the
heavy lifting (move generation, eval, TT, killer/history ordering); this
wrapper only translates protocol types and picks search limits from the
difficulty level and remaining clock budget.
"""
from __future__ import annotations

from dataclasses import dataclass

import omok_core

from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr


@dataclass(frozen=True)
class Difficulty:
    """Maps to (max_depth, default_budget_ms, root_width, child_width)."""
    name: str
    max_depth: int
    default_budget_ms: int
    root_width: int
    child_width: int


EASY   = Difficulty("easy",   max_depth=4, default_budget_ms=400,  root_width=12, child_width=8)
MEDIUM = Difficulty("medium", max_depth=6, default_budget_ms=1200, root_width=16, child_width=10)
HARD   = Difficulty("hard",   max_depth=8, default_budget_ms=2500, root_width=20, child_width=12)


def difficulty_from_name(name: str | None) -> Difficulty:
    n = (name or "").lower()
    if n in ("easy", "1"):   return EASY
    if n in ("hard", "3"):   return HARD
    return MEDIUM


class MinimaxAI:
    name = "minimax"

    def __init__(self, difficulty: Difficulty | str | None = None, tt_size_mb: int = 32) -> None:
        self.difficulty = difficulty if isinstance(difficulty, Difficulty) else difficulty_from_name(difficulty)
        self._searcher = omok_core.Searcher(tt_size_mb)
        self._rules = omok_core.RuleChecker()

    def choose_move(self, engine: Engine, color: ColorStr, budget_ms: int) -> tuple[int, int]:
        cpp_color = omok_core.Color.Black if color == ColorStr.BLACK else omok_core.Color.White
        lim = omok_core.SearchLimits()
        lim.max_depth   = self.difficulty.max_depth
        lim.budget_ms   = max(50, min(budget_ms, self.difficulty.default_budget_ms))
        lim.root_width  = self.difficulty.root_width
        lim.child_width = self.difficulty.child_width

        result = self._searcher.search(engine.board, cpp_color, self._rules, lim)
        r, c = result.best_r, result.best_c
        if r < 0 or c < 0:
            # Empty-board / pathological fallback: center.
            return (omok_core.BOARD_SIZE // 2, omok_core.BOARD_SIZE // 2)
        return (int(r), int(c))
