"""Clock invariants under simulated time progression."""
from __future__ import annotations

from omok_server.game.clock import GameClock
from omok_server.schemas import ColorStr


class FakeTime:
    def __init__(self, t0: int = 0) -> None:
        self.t = t0

    def __call__(self) -> int:
        return self.t

    def advance(self, ms: int) -> None:
        self.t += ms


def test_initial_state_is_5min_3x20s() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    assert clock.black.main_ms == 5 * 60 * 1000
    assert clock.black.byoyomi_periods == 3
    assert clock.black.byoyomi_ms == 20 * 1000
    assert clock.black.in_byoyomi is False


def test_quick_move_subtracts_main_time() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    ft.advance(3000)  # used 3 seconds
    clock.apply_move()
    assert clock.black.main_ms == 5 * 60 * 1000 - 3000
    assert clock.black.in_byoyomi is False
    assert clock.black.byoyomi_periods == 3


def test_overflow_into_byoyomi_keeps_periods_if_within_one_period() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # Burn main time + 10 seconds (less than one byo period of 20s).
    ft.advance(5 * 60 * 1000 + 10_000)
    clock.apply_move()
    assert clock.black.main_ms == 0
    assert clock.black.in_byoyomi is True
    assert clock.black.byoyomi_periods == 3
    assert clock.black.timed_out is False


def test_overflow_consumes_periods_one_at_a_time() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # Burn main time + 50 seconds (2.5 periods worth past main).
    ft.advance(5 * 60 * 1000 + 50_000)
    clock.apply_move()
    assert clock.black.main_ms == 0
    assert clock.black.in_byoyomi is True
    # 50s overflow: first 20s lands inside period 1 (no consumption), each
    # extra 20s consumes one. 50s → 2 full periods past the first → 2
    # consumed → 1 remaining.
    assert clock.black.byoyomi_periods == 1
    assert clock.black.timed_out is False


def test_running_out_all_periods_triggers_timeout_flag() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # Burn main + 4 full byo periods (80s, but only 3*20=60s are available)
    ft.advance(5 * 60 * 1000 + 80_000)
    clock.apply_move()
    assert clock.black.timed_out is True


def test_byoyomi_refresh_on_move_within_period() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    # Setup: place black in byo-yomi state directly.
    clock.black.main_ms = 0
    clock.black.in_byoyomi = True
    clock.start_turn(ColorStr.BLACK)
    ft.advance(15_000)  # 15s, within the 20s period
    clock.apply_move()
    # Period count unchanged, still 3.
    assert clock.black.byoyomi_periods == 3
    assert clock.black.in_byoyomi is True


def test_byoyomi_consumes_periods_on_overflow() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.black.main_ms = 0
    clock.black.in_byoyomi = True
    clock.start_turn(ColorStr.BLACK)
    ft.advance(50_000)  # 2.5 periods used
    clock.apply_move()
    # consumed = 50000 // 20000 = 2 → 3-2 = 1 period left.
    assert clock.black.byoyomi_periods == 1


def test_byoyomi_full_exhaust_during_byoyomi() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.black.main_ms = 0
    clock.black.in_byoyomi = True
    clock.start_turn(ColorStr.BLACK)
    ft.advance(70_000)  # 3 full 20s periods + overflow
    clock.apply_move()
    assert clock.black.timed_out is True


def test_check_timeout_during_active_turn() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # 5min + 70s = past main + 3 full 20s periods + 10s overflow.
    ft.advance(5 * 60 * 1000 + 70_000)
    timed = clock.check_timeout()
    assert timed == ColorStr.BLACK


def test_live_snapshot_for_active_side_deducts_elapsed() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    ft.advance(2000)
    snap = clock.live_snapshot_for(ColorStr.BLACK)
    assert snap.main_ms == 5 * 60 * 1000 - 2000
    assert snap.in_byoyomi is False
    # Inactive side untouched.
    snap_w = clock.live_snapshot_for(ColorStr.WHITE)
    assert snap_w.main_ms == 5 * 60 * 1000


# ----- Bug-fix coverage for v1.4.1 (state advances mid-turn) -----

def test_main_to_byoyomi_transition_visible_without_move() -> None:
    """The instant elapsed crosses main_ms, the snapshot must show
    in_byoyomi=True. Previously this only happened when the active side
    actually played a move, leaving the UI stuck on '0:00 main'."""
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    ft.advance(5 * 60 * 1000 + 1)  # 0.001s past main
    snap = clock.live_snapshot_for(ColorStr.BLACK)
    assert snap.in_byoyomi is True
    assert snap.main_ms == 0
    # Still inside the first byo-yomi period.
    assert snap.byoyomi_periods == 3


def test_one_period_elapsed_without_move_does_not_timeout() -> None:
    """Letting one full 20s byo-yomi period elapse should consume one
    period but NOT end the game (3 → 2 periods remaining)."""
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # Cross main + one full byo-yomi period (20s) without playing.
    ft.advance(5 * 60 * 1000 + 20_000 + 1)
    assert clock.check_timeout() is None
    assert clock.black.in_byoyomi is True
    assert clock.black.byoyomi_periods == 2


def test_two_periods_elapsed_consumes_two_periods_no_timeout() -> None:
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    ft.advance(5 * 60 * 1000 + 40_000 + 1)
    assert clock.check_timeout() is None
    assert clock.black.byoyomi_periods == 1


def test_all_three_periods_required_for_timeout() -> None:
    """Crossing the third period boundary AND running into a fourth is
    what should fire timeout."""
    ft = FakeTime()
    clock = GameClock(now=ft)
    clock.start_turn(ColorStr.BLACK)
    # main + 60s byo-yomi total = 6m. Stop right at the edge.
    ft.advance(5 * 60 * 1000 + 60_000)
    assert clock.check_timeout() is None  # exactly at the boundary
    # 0.001s past → timeout.
    ft.advance(1)
    assert clock.check_timeout() == ColorStr.BLACK
    assert clock.black.timed_out is True
