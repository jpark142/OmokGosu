"""Chess-clock with Japanese-style byo-yomi.

Server-authoritative: every clock query takes a `now_ms` so the caller controls
the time source (real monotonic in production, fake in tests).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from omok_server.schemas import ClockSnapshot, ColorStr

DEFAULT_MAIN_MS = 5 * 60 * 1000  # 5 minutes
DEFAULT_BYOYOMI_MS = 10 * 1000  # 10 seconds
DEFAULT_BYOYOMI_PERIODS = 3


def now_monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


@dataclass
class ClockSide:
    main_ms: int = DEFAULT_MAIN_MS
    byoyomi_ms: int = DEFAULT_BYOYOMI_MS
    byoyomi_periods: int = DEFAULT_BYOYOMI_PERIODS
    in_byoyomi: bool = False
    timed_out: bool = False

    def snapshot(self) -> ClockSnapshot:
        return ClockSnapshot(
            main_ms=max(0, self.main_ms),
            byoyomi_periods=max(0, self.byoyomi_periods),
            byoyomi_ms=self.byoyomi_ms,
            in_byoyomi=self.in_byoyomi,
        )


@dataclass
class GameClock:
    """Two ClockSides + which side's turn is running."""

    black: ClockSide = field(default_factory=ClockSide)
    white: ClockSide = field(default_factory=ClockSide)
    active: ColorStr | None = None
    turn_started_at_ms: int | None = None

    now: Callable[[], int] = field(default=now_monotonic_ms)

    def start_turn(self, color: ColorStr) -> None:
        self.active = color
        self.turn_started_at_ms = self.now()

    def side(self, color: ColorStr) -> ClockSide:
        return self.black if color == ColorStr.BLACK else self.white

    def _elapsed_ms(self) -> int:
        if self.turn_started_at_ms is None:
            return 0
        return self.now() - self.turn_started_at_ms

    def remaining_for_active(self) -> int:
        """Remaining ms in the *current portion* (main if not in byo-yomi, else byo period)."""
        if self.active is None:
            return 0
        s = self.side(self.active)
        elapsed = self._elapsed_ms()
        if not s.in_byoyomi:
            return max(0, s.main_ms - elapsed)
        return max(0, s.byoyomi_ms - elapsed)

    @staticmethod
    def _consume_byoyomi(s: "ClockSide", elapsed_in_byoyomi: int) -> None:
        """Apply Japanese-style byo-yomi consumption for a single move.

        Rules: with N periods of P seconds and elapsed time T in byo-yomi,
          T ≤ P             → 0 periods consumed (period refreshes next turn).
          k*P < T ≤ (k+1)*P → k periods consumed (1 ≤ k ≤ N-1).
          T > N*P           → all N consumed + flag timed_out.
        """
        P = s.byoyomi_ms
        if P <= 0 or elapsed_in_byoyomi <= P:
            # Free refresh (Japanese rule): finishing within one period costs nothing.
            return
        # ceil(T / P) − 1 = number of periods *used up* by this turn beyond the first.
        consumed = (elapsed_in_byoyomi - 1) // P
        if consumed >= s.byoyomi_periods:
            s.byoyomi_periods = 0
            s.timed_out = True
        else:
            s.byoyomi_periods -= consumed

    def _advance_state(self) -> None:
        """Sync the active side's state to wall-clock time WITHOUT ending
        the turn. Idempotent — safe to call before any read.

        Two transitions can fire without a move:

          1. main_ms → 0 the instant elapsed reaches the original main
             budget. We rebase turn_started_at so subsequent elapsed
             calculations measure from "byo-yomi start," and flip
             in_byoyomi = True. The user sees the byo-yomi clock the
             moment their main runs out, not on their next move.

          2. byo-yomi period boundary. The active side that lets a full
             10s period elapse without playing has spent it; we
             decrement byoyomi_periods and rebase turn_started_at to
             the start of the next period. (This is the standard
             Japanese byo-yomi rule: free refresh within the period,
             one period consumed each time you cross a boundary.)

        Callers must hold no logical invariants other than "the active
        side is still up to move" — this function never marks a side as
        timed out or ends the turn. Timeout detection stays in
        check_timeout, and turn-end stays in apply_move.
        """
        if self.active is None or self.turn_started_at_ms is None:
            return
        s = self.side(self.active)
        P = s.byoyomi_ms
        if P <= 0:
            return

        # 1. Cross from main into byo-yomi if elapsed has overrun main_ms.
        if not s.in_byoyomi:
            elapsed = self._elapsed_ms()
            if elapsed < s.main_ms:
                return  # still inside main time
            overflow = elapsed - s.main_ms
            # Rebase: pretend the turn began at the moment main ran out.
            # `now() - overflow` is that wall-clock instant.
            self.turn_started_at_ms = self.now() - overflow
            s.main_ms = 0
            s.in_byoyomi = True
            # Fall through; if overflow > P we also need to consume periods.

        # 2. Consume any whole byo-yomi periods this turn has used up.
        elapsed_in_byo = self._elapsed_ms()
        if elapsed_in_byo <= P:
            return
        k = elapsed_in_byo // P
        # Clamp: never reduce below 1 here, because reaching 0 means the
        # final period has fully elapsed → that's timeout territory, owned
        # by check_timeout. We leave byoyomi_periods at 1 with elapsed
        # still pointing past P, and check_timeout will flag it.
        consumable = min(k, max(0, s.byoyomi_periods - 1))
        if consumable == 0:
            return
        s.byoyomi_periods -= consumable
        self.turn_started_at_ms += consumable * P

    def apply_move(self) -> None:
        """Consume time used during the active side's turn and stop the clock.

        After this returns, `self.active` is cleared. Call `start_turn(opponent)` to
        resume on the other side.
        """
        if self.active is None or self.turn_started_at_ms is None:
            return
        # Bring state up to date so apply_move only has to handle the
        # "within current period" or "still inside main" cases.
        self._advance_state()
        s = self.side(self.active)
        elapsed = self._elapsed_ms()

        if not s.in_byoyomi:
            # Still inside main time. Deduct what was used.
            s.main_ms = max(0, s.main_ms - elapsed)
        else:
            # In byo-yomi: free refresh if we moved within the current
            # period (elapsed_in_byo ≤ P). _advance_state has already
            # consumed any crossed periods.
            if elapsed > s.byoyomi_ms:
                # Should not happen — _advance_state would have caught it
                # by either consuming a period or leaving timeout to
                # check_timeout. But guard anyway.
                self._consume_byoyomi(s, elapsed)

        self.active = None
        self.turn_started_at_ms = None

    def check_timeout(self) -> ColorStr | None:
        """Return the color that has timed out, if any (active side only).

        Always advances state first so the boundary check sees an accurate
        in_byoyomi / byoyomi_periods picture.
        """
        if self.active is None:
            return None
        self._advance_state()
        s = self.side(self.active)
        elapsed = self._elapsed_ms()
        if not s.in_byoyomi:
            # Still in main time — _advance_state would have flipped us if
            # we'd overrun. So this branch only fires while main is alive.
            return None
        # In byo-yomi. _advance_state has already consumed all crossable
        # periods; the only way to time out is to overrun the LAST period.
        if s.byoyomi_periods <= 0:
            s.timed_out = True
            return self.active
        if s.byoyomi_periods == 1 and self._elapsed_ms() > s.byoyomi_ms:
            s.byoyomi_periods = 0
            s.timed_out = True
            return self.active
        # Fall-through: also handle the degenerate case of periods > 1 +
        # elapsed past the period — _advance_state would have consumed,
        # but defensively check.
        if elapsed > s.byoyomi_periods * s.byoyomi_ms:
            s.byoyomi_periods = 0
            s.timed_out = True
            return self.active
        return None

    def live_snapshot_for(self, color: ColorStr) -> ClockSnapshot:
        """Snapshot reflecting *live* remaining time for the given color.

        For the active side, deducts the in-progress elapsed ms from the appropriate bucket.
        For the inactive side, returns the static snapshot.

        Advances state first so the snapshot always reflects the latest
        in_byoyomi / byoyomi_periods (otherwise a viewer would see a frozen
        "5:00 main" right after main ran out, until the next move landed).
        """
        if color == self.active:
            self._advance_state()
        s = self.side(color)
        if color != self.active:
            return s.snapshot()
        elapsed = self._elapsed_ms()
        if not s.in_byoyomi:
            remaining_main = max(0, s.main_ms - elapsed)
            if remaining_main > 0:
                return ClockSnapshot(
                    main_ms=remaining_main,
                    byoyomi_periods=s.byoyomi_periods,
                    byoyomi_ms=s.byoyomi_ms,
                    in_byoyomi=False,
                )
            # spilled into byo-yomi
            overflow = elapsed - s.main_ms
            periods_used = overflow // s.byoyomi_ms
            current_period_used = overflow - periods_used * s.byoyomi_ms
            periods_left = max(0, s.byoyomi_periods - periods_used)
            return ClockSnapshot(
                main_ms=0,
                byoyomi_periods=periods_left,
                byoyomi_ms=max(0, s.byoyomi_ms - current_period_used),
                in_byoyomi=True,
            )
        else:
            periods_used = elapsed // s.byoyomi_ms
            current_period_used = elapsed - periods_used * s.byoyomi_ms
            periods_left = max(0, s.byoyomi_periods - periods_used)
            return ClockSnapshot(
                main_ms=0,
                byoyomi_periods=periods_left,
                byoyomi_ms=max(0, s.byoyomi_ms - current_period_used),
                in_byoyomi=True,
            )
