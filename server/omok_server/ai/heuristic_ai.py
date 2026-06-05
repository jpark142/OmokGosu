"""Heuristic AI: strong amateur level by layering forcing-move search on top of Minimax.

Decision order per move:
  1. Immediate win — if any move creates 5-in-a-row, play it.
  2. Block immediate loss — if opponent can win next turn, block.
  3. VCF (Victory by Continuous Fours) — DFS for a forced winning sequence using
     moves that all create fours. Cheap and decisive when it exists.
  4. Block opponent's VCF — search VCF from opponent's perspective; if they have
     one, the first move of their sequence is the threat we must defuse.
  5. Fall back to Minimax (α-β + ID, the Phase 2 engine).

VCT (open-three threats too) is intentionally skipped — the additional branching
makes it slower and the marginal value over VCF+Minimax is small for a casual
opponent. Revisit when we want to push past strong-amateur.
"""
from __future__ import annotations

from dataclasses import dataclass

import omok_core

from omok_server.ai.minimax_ai import MinimaxAI, Difficulty, difficulty_from_name
from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr


def _cpp_color(c: ColorStr) -> "omok_core.Color":
    return omok_core.Color.Black if c == ColorStr.BLACK else omok_core.Color.White


def _candidate_cells(board: "omok_core.Board", radius: int = 2) -> list[tuple[int, int]]:
    """Empty cells within Chebyshev `radius` of any stone. Center on empty board."""
    B = omok_core.BOARD_SIZE
    if board.move_count == 0:
        return [(B // 2, B // 2)]
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for r, c, _ in board.history():
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < B and 0 <= nc < B and (nr, nc) not in seen:
                    if board.is_empty(nr, nc):
                        seen.add((nr, nc))
                        out.append((nr, nc))
    return out


@dataclass(frozen=True)
class HeuristicConfig:
    vcf_depth: int = 14
    minimax: Difficulty | None = None  # default: MEDIUM


class HeuristicAI:
    name = "heuristic"

    def __init__(self, difficulty: Difficulty | str | None = None) -> None:
        diff = difficulty if isinstance(difficulty, Difficulty) else difficulty_from_name(difficulty)
        self._cfg = HeuristicConfig(minimax=diff)
        self._fallback = MinimaxAI(difficulty=diff)
        self._rules = omok_core.RuleChecker()

    def choose_move(self, engine: Engine, color: ColorStr, budget_ms: int) -> tuple[int, int]:
        board = engine.board
        me = _cpp_color(color)
        opp_color: ColorStr = ColorStr.WHITE if color == ColorStr.BLACK else ColorStr.BLACK
        opp = _cpp_color(opp_color)

        forbidden: set[tuple[int, int]] = set()
        if color == ColorStr.BLACK:
            forbidden = set(engine.forbidden_squares())

        cands = _candidate_cells(board)

        # 1. Immediate win.
        for r, c in cands:
            if (r, c) in forbidden:
                continue
            if self._rules.is_winning_move(board, r, c, me):
                return (r, c)

        # 2. Block opponent's immediate win.
        for r, c in cands:
            if self._rules.is_winning_move(board, r, c, opp):
                # Playing here blocks the win. If that move is forbidden for us
                # (we're black), we have no legal block — fall through.
                if (r, c) not in forbidden:
                    return (r, c)

        # 3. Our VCF.
        found, seq, _ = omok_core.find_vcf(board, me, self._cfg.vcf_depth)
        if found and seq:
            r, c = seq[0]
            if (r, c) not in forbidden:
                return (r, c)

        # 4. Block opponent's VCF — defuse the first move of their forced sequence.
        found, seq, _ = omok_core.find_vcf(board, opp, self._cfg.vcf_depth)
        if found and seq:
            r, c = seq[0]
            if (r, c) not in forbidden:
                return (r, c)

        # 5. Fall through to Minimax.
        return self._fallback.choose_move(engine, color, budget_ms)
