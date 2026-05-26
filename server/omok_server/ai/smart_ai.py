"""Greedy one-ply AI: scores every candidate by pattern strength after playing it.

This is Phase 1.5 — not the full Minimax of Phase 2, but enough to make the AI
actually try to win and block instead of moving randomly.

Algorithm:
  for each candidate near existing stones (and not Renju-forbidden if black):
      offensive_score = pattern_score(virtually play me at candidate)
      defensive_score = pattern_score(virtually play opponent at candidate)
      total = offensive_score + 0.9 * defensive_score
  pick the move with max total

`pattern_score` counts the best threat created in each of 4 directions through
the candidate (five > open-four > four > open-three > open-two), weighted by
the standard Renju-AI gomoku weights.
"""
from __future__ import annotations

import omok_core

from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr


# --- threat weights (offense from candidate's perspective) ---

W_FIVE = 1_000_000
W_OVERLINE_BLACK_PENALTY = -100_000  # creating 6+ as black is suicide / forbidden
W_OPEN_FOUR = 100_000
W_DOUBLE_FOUR = 80_000
W_FOUR_PLUS_OPEN_THREE = 60_000
W_DOUBLE_OPEN_THREE = 30_000
W_FOUR = 5_000
W_OPEN_THREE = 2_000
W_CLOSED_THREE = 300
W_OPEN_TWO = 50


def _at(board: "omok_core.Board", r: int, c: int) -> int:
    if r < 0 or r >= omok_core.BOARD_SIZE or c < 0 or c >= omok_core.BOARD_SIZE:
        return -1
    return int(board.at(r, c))


def _evaluate_after_play(board: "omok_core.Board", r: int, c: int, color: "omok_core.Color") -> int:
    """Score the board after virtually playing `color` at (r,c). Move is undone before return.

    Returns 0 if the cell is occupied. Score = best threat created (per the weights above).
    """
    if not board.is_empty(r, c):
        return 0

    ok = board.play(r, c, color)
    if not ok:
        return 0

    own = int(color)
    is_black = color == omok_core.Color.Black

    creates_five = False
    overline = False
    open_fours = 0
    fours = 0
    open_threes = 0
    closed_threes = 0
    open_twos = 0

    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        # Walk back to start of run, walk forward to end of run (own stones only).
        rs, cs = r, c
        while _at(board, rs - dr, cs - dc) == own:
            rs -= dr
            cs -= dc
        re, ce = r, c
        while _at(board, re + dr, ce + dc) == own:
            re += dr
            ce += dc
        run = 1
        if dr == 0:
            run = abs(ce - cs) + 1
        elif dc == 0:
            run = abs(re - rs) + 1
        else:
            run = abs(re - rs) + 1

        if run >= 5:
            if run == 5:
                creates_five = True
            else:
                # 6+ in a row
                if is_black:
                    overline = True
                else:
                    creates_five = True  # white wins on overline too
            continue

        before = _at(board, rs - dr, cs - dc)
        after = _at(board, re + dr, ce + dc)
        left_open = before == 0
        right_open = after == 0

        if run == 4:
            if left_open and right_open:
                open_fours += 1
            elif left_open or right_open:
                fours += 1
            # else: fully blocked four — no threat
            continue

        if run == 3:
            # Open three needs space for both extensions plus another empty beyond at least one side.
            # Simple rule: both immediate neighbors empty AND at least one of the next-to-immediate cells empty.
            if left_open and right_open:
                far_left = _at(board, rs - 2 * dr, cs - 2 * dc)
                far_right = _at(board, re + 2 * dr, ce + 2 * dc)
                if far_left == 0 or far_right == 0:
                    open_threes += 1
                else:
                    closed_threes += 1
            elif left_open or right_open:
                closed_threes += 1
            continue

        if run == 2:
            far_left = _at(board, rs - 2 * dr, cs - 2 * dc)
            far_right = _at(board, re + 2 * dr, ce + 2 * dc)
            if left_open and right_open and (far_left == 0 or far_right == 0):
                open_twos += 1
            continue

    board.undo()

    if creates_five:
        return W_FIVE
    if overline:
        return W_OVERLINE_BLACK_PENALTY
    if open_fours >= 1:
        return W_OPEN_FOUR
    if fours >= 2:
        return W_DOUBLE_FOUR
    if fours >= 1 and open_threes >= 1:
        return W_FOUR_PLUS_OPEN_THREE
    if open_threes >= 2:
        return W_DOUBLE_OPEN_THREE
    if fours >= 1:
        return W_FOUR
    if open_threes >= 1:
        return W_OPEN_THREE
    if closed_threes >= 1:
        return W_CLOSED_THREE
    if open_twos >= 1:
        return W_OPEN_TWO
    return 1


def _candidates(board: "omok_core.Board") -> list[tuple[int, int]]:
    """Empty cells within Chebyshev distance 2 of any occupied cell."""
    BOARD = omok_core.BOARD_SIZE
    occupied: list[tuple[int, int]] = []
    for r, c, _ in board.history():
        occupied.append((r, c))
    if not occupied:
        return [(BOARD // 2, BOARD // 2)]
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for or_, oc in occupied:
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                nr, nc = or_ + dr, oc + dc
                if 0 <= nr < BOARD and 0 <= nc < BOARD and board.is_empty(nr, nc):
                    key = (nr, nc)
                    if key not in seen:
                        seen.add(key)
                        out.append(key)
    return out


class SmartAI:
    name = "smart"

    def choose_move(self, engine: Engine, color: ColorStr, budget_ms: int) -> tuple[int, int]:
        del budget_ms  # greedy; budget not used yet
        board = engine.board
        cpp_color = omok_core.Color.Black if color == ColorStr.BLACK else omok_core.Color.White
        cpp_opp = omok_core.Color.White if color == ColorStr.BLACK else omok_core.Color.Black

        forbidden: set[tuple[int, int]] = set()
        if color == ColorStr.BLACK:
            forbidden = set(engine.forbidden_squares())

        candidates = _candidates(board)

        best_score = -10**18
        best_move: tuple[int, int] | None = None
        for r, c in candidates:
            if (r, c) in forbidden:
                continue
            offense = _evaluate_after_play(board, r, c, cpp_color)
            defense = _evaluate_after_play(board, r, c, cpp_opp)
            score = offense + (defense * 9) // 10
            if score > best_score:
                best_score = score
                best_move = (r, c)

        if best_move is None:
            # Fallback: any legal empty cell. Should not happen on a normal 15x15.
            for r in range(omok_core.BOARD_SIZE):
                for c in range(omok_core.BOARD_SIZE):
                    if board.is_empty(r, c) and (r, c) not in forbidden:
                        return (r, c)
            return (omok_core.BOARD_SIZE // 2, omok_core.BOARD_SIZE // 2)

        return best_move
