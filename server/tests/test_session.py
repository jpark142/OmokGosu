"""GameSession state machine."""
from __future__ import annotations

from omok_server.game.session import GameSession
from omok_server.schemas import (
    ColorStr,
    ForbiddenReason,
    GameMode,
    GameOverReason,
    GameStatus,
)


def test_new_session_has_two_players_black_to_move() -> None:
    gs = GameSession.new(mode=GameMode.HVH)
    assert gs.status == GameStatus.IN_PROGRESS
    assert gs.engine.side_to_move == ColorStr.BLACK
    assert set(gs.players.keys()) == {ColorStr.BLACK, ColorStr.WHITE}


def test_apply_move_rejects_wrong_turn() -> None:
    gs = GameSession.new()
    reason = gs.apply_move(7, 7, ColorStr.WHITE)
    assert reason == ForbiddenReason.NOT_YOUR_TURN


def test_apply_move_rejects_forbidden_double_three() -> None:
    gs = GameSession.new()
    # Set up double-three pattern via direct play (bypass turn alternation by playing white in between).
    moves = [
        (7, 5, ColorStr.BLACK), (0, 0, ColorStr.WHITE),
        (7, 6, ColorStr.BLACK), (0, 1, ColorStr.WHITE),
        (5, 7, ColorStr.BLACK), (0, 2, ColorStr.WHITE),
        (6, 7, ColorStr.BLACK), (0, 3, ColorStr.WHITE),
    ]
    for r, c, color in moves:
        reason = gs.apply_move(r, c, color)
        assert reason is None, f"unexpected reject at ({r},{c},{color}): {reason}"
    # Now black to move; 7,7 is the double-three square.
    reason = gs.apply_move(7, 7, ColorStr.BLACK)
    assert reason == ForbiddenReason.DOUBLE_THREE
    assert gs.status == GameStatus.IN_PROGRESS  # forbidden does NOT end the game


def test_apply_move_ends_game_on_black_five() -> None:
    gs = GameSession.new()
    moves = [
        (7, 3, ColorStr.BLACK), (0, 0, ColorStr.WHITE),
        (7, 4, ColorStr.BLACK), (0, 1, ColorStr.WHITE),
        (7, 5, ColorStr.BLACK), (0, 2, ColorStr.WHITE),
        (7, 6, ColorStr.BLACK), (0, 3, ColorStr.WHITE),
        (7, 7, ColorStr.BLACK),
    ]
    for r, c, color in moves:
        reason = gs.apply_move(r, c, color)
        assert reason is None
    assert gs.status == GameStatus.OVER
    assert gs.winner == ColorStr.BLACK
    assert gs.over_reason == GameOverReason.FIVE


def test_resign_ends_game() -> None:
    gs = GameSession.new()
    gs.resign(ColorStr.BLACK)
    assert gs.status == GameStatus.OVER
    assert gs.winner == ColorStr.WHITE
    assert gs.over_reason == GameOverReason.RESIGN


def test_state_msg_includes_forbidden_squares_when_black_to_move() -> None:
    gs = GameSession.new()
    msg = gs.to_state_msg()
    assert msg.to_move == ColorStr.BLACK
    # Forbidden squares present (possibly empty list, but the field exists and is a list).
    assert isinstance(msg.forbidden_squares, list)


def test_state_msg_no_forbidden_when_white_to_move() -> None:
    gs = GameSession.new()
    gs.apply_move(7, 7, ColorStr.BLACK)
    msg = gs.to_state_msg()
    assert msg.to_move == ColorStr.WHITE
    assert msg.forbidden_squares == []
