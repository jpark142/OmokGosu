"""Thin wrapper around the `omok_core` C++ module.

Translates between python ColorStr enum and the C++ Color enum, and exposes
high-level operations the rest of the server cares about (play, validate,
forbidden squares, win check).
"""
from __future__ import annotations

from typing import Iterable

import omok_core

from omok_server.schemas import ColorStr, ForbiddenReason, Stone


def _py_to_cpp_color(c: ColorStr) -> omok_core.Color:
    return omok_core.Color.Black if c == ColorStr.BLACK else omok_core.Color.White


def _cpp_to_py_color(c: omok_core.Color) -> ColorStr:
    if c == omok_core.Color.Black:
        return ColorStr.BLACK
    return ColorStr.WHITE


class Engine:
    """Owns one Board + RuleChecker, mirrors Stone state for serialization."""

    def __init__(self) -> None:
        self._board = omok_core.Board()
        self._rules = omok_core.RuleChecker()

    # --- queries ---

    @property
    def board(self) -> omok_core.Board:
        return self._board

    @property
    def side_to_move(self) -> ColorStr:
        return _cpp_to_py_color(self._board.side_to_move)

    @property
    def move_number(self) -> int:
        return self._board.move_count

    def stones(self) -> list[Stone]:
        result: list[Stone] = []
        for (r, c, color_int) in self._board.history():
            color = omok_core.Color(color_int)
            result.append(Stone(r=r, c=c, color=_cpp_to_py_color(color)))
        return result

    def last_move(self) -> Stone | None:
        hist = self._board.history()
        if not hist:
            return None
        r, c, color_int = hist[-1]
        return Stone(r=r, c=c, color=_cpp_to_py_color(omok_core.Color(color_int)))

    def forbidden_squares(self) -> list[tuple[int, int]]:
        """Returns Renju-forbidden squares for the side currently to move.

        Empty list if white to move.
        """
        cpp_color = _py_to_cpp_color(self.side_to_move)
        return self._rules.compute_forbidden_squares(self._board, cpp_color)

    # --- mutations ---

    def validate(self, r: int, c: int, color: ColorStr) -> ForbiddenReason | None:
        """Pre-check a candidate move. Returns reason if invalid, None if OK."""
        if r < 0 or r >= omok_core.BOARD_SIZE or c < 0 or c >= omok_core.BOARD_SIZE:
            return ForbiddenReason.OUT_OF_BOUNDS
        if not self._board.is_empty(r, c):
            return ForbiddenReason.OCCUPIED
        if color != self.side_to_move:
            return ForbiddenReason.NOT_YOUR_TURN
        if color == ColorStr.BLACK:
            kind = self._rules.classify_for_black(self._board, r, c)
            if kind == omok_core.ForbiddenKind.DoubleThree:
                return ForbiddenReason.DOUBLE_THREE
            if kind == omok_core.ForbiddenKind.DoubleFour:
                return ForbiddenReason.DOUBLE_FOUR
            if kind == omok_core.ForbiddenKind.Overline:
                return ForbiddenReason.OVERLINE
        return None

    def play(self, r: int, c: int, color: ColorStr) -> bool:
        """Apply the move unconditionally. Caller must `validate` first."""
        return self._board.play(r, c, _py_to_cpp_color(color))

    def last_move_wins(self) -> bool:
        return self._rules.last_move_wins(self._board)

    def last_move_was_overline_for_white(self) -> bool:
        """White-only: did the last move create a 6+ run (overline win for white)?"""
        if self.move_number == 0:
            return False
        r, c, color_int = self._board.history()[-1]
        if omok_core.Color(color_int) != omok_core.Color.White:
            return False
        # last_move_wins returns True for any 5+ run by white. To distinguish
        # exact-5 from overline isn't strictly needed (both are a win), but we keep
        # the hook for the UI to render the right reason if we ever want to.
        return self._rules.last_move_wins(self._board)

    # --- helpers for tests / replay ---

    def setup_position(self, stones: Iterable[Stone]) -> None:
        """Force a position by playing stones in order. Bypasses validate."""
        self._board.reset()
        for s in stones:
            self._board.play(s.r, s.c, _py_to_cpp_color(s.color))

    def reset(self) -> None:
        self._board.reset()
