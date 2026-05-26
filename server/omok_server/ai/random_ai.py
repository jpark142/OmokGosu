"""Random-move AI: picks any legal square (respects Renju for black).

Phase 1 smoke implementation — enough to verify HVA wiring end-to-end.
"""
from __future__ import annotations

import random

import omok_core

from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr


class RandomAI:
    name = "random"

    def choose_move(self, engine: Engine, color: ColorStr, budget_ms: int) -> tuple[int, int]:
        del budget_ms  # random is instant
        board = engine.board
        legal: list[tuple[int, int]] = []
        forbidden: set[tuple[int, int]] = set()
        if color == ColorStr.BLACK:
            forbidden = set(engine.forbidden_squares())
        for r in range(omok_core.BOARD_SIZE):
            for c in range(omok_core.BOARD_SIZE):
                if not board.is_empty(r, c):
                    continue
                if (r, c) in forbidden:
                    continue
                legal.append((r, c))
        if not legal:
            # No legal move (extremely degenerate state). Fallback to center.
            return (omok_core.BOARD_SIZE // 2, omok_core.BOARD_SIZE // 2)
        return random.choice(legal)
