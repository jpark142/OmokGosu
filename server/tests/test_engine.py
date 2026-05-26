"""Engine wraps omok_core correctly."""
from __future__ import annotations

from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr, ForbiddenReason


def test_engine_starts_black_to_move() -> None:
    e = Engine()
    assert e.side_to_move == ColorStr.BLACK
    assert e.move_number == 0
    assert e.stones() == []
    assert e.last_move() is None


def test_validate_rejects_out_of_bounds() -> None:
    e = Engine()
    assert e.validate(-1, 0, ColorStr.BLACK) == ForbiddenReason.OUT_OF_BOUNDS
    assert e.validate(0, 15, ColorStr.BLACK) == ForbiddenReason.OUT_OF_BOUNDS


def test_validate_rejects_wrong_turn() -> None:
    e = Engine()
    assert e.validate(7, 7, ColorStr.WHITE) == ForbiddenReason.NOT_YOUR_TURN


def test_validate_rejects_occupied() -> None:
    e = Engine()
    e.play(7, 7, ColorStr.BLACK)
    assert e.validate(7, 7, ColorStr.WHITE) == ForbiddenReason.OCCUPIED


def test_play_alternates_side_to_move() -> None:
    e = Engine()
    e.play(7, 7, ColorStr.BLACK)
    assert e.side_to_move == ColorStr.WHITE
    e.play(7, 8, ColorStr.WHITE)
    assert e.side_to_move == ColorStr.BLACK


def test_last_move_wins_for_black_five() -> None:
    e = Engine()
    for r, c, color in [
        (7, 3, ColorStr.BLACK), (0, 0, ColorStr.WHITE),
        (7, 4, ColorStr.BLACK), (0, 1, ColorStr.WHITE),
        (7, 5, ColorStr.BLACK), (0, 2, ColorStr.WHITE),
        (7, 6, ColorStr.BLACK), (0, 3, ColorStr.WHITE),
        (7, 7, ColorStr.BLACK),
    ]:
        e.play(r, c, color)
    assert e.last_move_wins() is True


def test_forbidden_double_three_detected() -> None:
    e = Engine()
    for r, c, color in [
        (7, 5, ColorStr.BLACK), (0, 0, ColorStr.WHITE),
        (7, 6, ColorStr.BLACK), (0, 1, ColorStr.WHITE),
        (5, 7, ColorStr.BLACK), (0, 2, ColorStr.WHITE),
        (6, 7, ColorStr.BLACK),
    ]:
        e.play(r, c, color)
    # Now white moves; sim a white tempo to put black to move.
    e.play(0, 3, ColorStr.WHITE)
    assert e.side_to_move == ColorStr.BLACK
    assert e.validate(7, 7, ColorStr.BLACK) == ForbiddenReason.DOUBLE_THREE


def test_forbidden_squares_empty_for_white_to_move() -> None:
    e = Engine()
    e.play(7, 7, ColorStr.BLACK)
    assert e.side_to_move == ColorStr.WHITE
    assert e.forbidden_squares() == []
