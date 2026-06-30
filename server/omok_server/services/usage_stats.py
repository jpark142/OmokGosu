"""Compute usage analytics from the SessionLog capture table.

SessionLog records one row per online session (connect → disconnect). This
module turns that raw log into the numbers a small dashboard / report wants:
daily active users, cumulative unique users, new users, peak concurrent, and
D+1 / D+7 retention by signup cohort.

Design notes:
  * All day-bucketing is done in **KST (Asia/Seoul)**. `connected_at` is stored
    as naive UTC (``datetime.utcnow()``), so we attach UTC then convert. Korean
    players expect "today" to mean a Korean calendar day, not a UTC one.
  * We load the whole table and aggregate in Python. Retention needs each
    user's first-ever active day *and* their full set of active days, which is
    awkward in one SQL pass over SQLite; at this app's scale (thousands of rows)
    a single full scan is cheap and far easier to keep correct. If the table
    ever gets large this becomes the place to push work back into SQL.
  * "First-ever active day" is only as old as SessionLog itself. Users active
    before logging began get a cohort date of their first *logged* session, so
    cohorts before the logging-start date are not meaningful. `data_since`
    surfaces that boundary to the caller.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from omok_server.db.engine import engine
from omok_server.db.models import SessionLog

# KST is a fixed +09:00 offset (no DST), so a plain timezone suffices — no need
# to pull in zoneinfo / tzdata, which isn't always present on slim images.
KST = timezone(timedelta(hours=9))
_UTC = timezone.utc


def _to_kst(dt: datetime) -> datetime:
    """Interpret a stored (naive, UTC) timestamp as an aware KST datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(KST)


@dataclass
class DailyRow:
    day: date
    dau: int = 0                 # distinct users active that KST day
    new_users: int = 0          # users whose first-ever active day is this day
    cumulative_users: int = 0   # distinct users active on or before this day
    peak_concurrent: int = 0    # max simultaneous open sessions during the day


@dataclass
class CohortRow:
    cohort_day: date
    size: int                   # users whose first active day is this day
    d1_retained: int | None = None  # came back on day+1 (None = not yet mature)
    d1_rate: float | None = None
    d7_retained: int | None = None
    d7_retained_rate: float | None = None  # filled as d7_rate below


@dataclass
class UsageStats:
    generated_at: datetime
    timezone: str
    data_since: date | None      # first KST day with any session
    today: date                  # latest KST day in range (capture cutoff)
    total_users: int             # distinct users ever seen
    dau_today: int
    wau: int                     # distinct users in the trailing 7 days
    mau: int                     # distinct users in the trailing 30 days
    overall_d1_rate: float | None
    overall_d7_rate: float | None
    daily: list[DailyRow] = field(default_factory=list)
    cohorts: list[CohortRow] = field(default_factory=list)


def _load_sessions() -> list[tuple[int, datetime, datetime | None]]:
    with Session(engine) as db:
        rows = db.exec(select(SessionLog)).all()
    return [(r.user_id, r.connected_at, r.disconnected_at) for r in rows]


def _peak_concurrent(intervals: list[tuple[datetime, datetime]]) -> int:
    """Max overlapping count via a +1/-1 sweep over interval endpoints."""
    events: list[tuple[datetime, int]] = []
    for start, end in intervals:
        events.append((start, 1))
        # End ties must close before a new one opens at the same instant so a
        # zero-length (orphan) session doesn't show as a phantom overlap.
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], e[1]))
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def compute(*, now: datetime | None = None) -> UsageStats:
    """Aggregate SessionLog into a UsageStats snapshot.

    `now` is injectable for tests; defaults to the real current time. It only
    sets the upper bound of the day range and the "maturity" cutoff for D+1/D+7
    (a cohort's retention is only counted once enough days have elapsed)."""
    now_kst = _to_kst(now if now is not None else datetime.now(_UTC))
    today = now_kst.date()

    sessions = _load_sessions()

    # Per-user set of active KST days, and per-day session intervals (for peak).
    user_days: dict[int, set[date]] = defaultdict(set)
    day_intervals: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
    for user_id, connected_at, disconnected_at in sessions:
        c_kst = _to_kst(connected_at)
        day = c_kst.date()
        user_days[user_id].add(day)
        # For concurrency we only need same-day overlap; clamp an open/cross-day
        # session's end to end-of-day (good enough for a per-day peak).
        end_kst = _to_kst(disconnected_at) if disconnected_at is not None else now_kst
        if end_kst < c_kst:
            end_kst = c_kst
        day_intervals[day].append((c_kst, end_kst))

    if not user_days:
        return UsageStats(
            generated_at=datetime.now(_UTC),
            timezone="Asia/Seoul (KST, UTC+9)",
            data_since=None,
            today=today,
            total_users=0,
            dau_today=0,
            wau=0,
            mau=0,
            overall_d1_rate=None,
            overall_d7_rate=None,
        )

    first_day: dict[int, date] = {u: min(days) for u, days in user_days.items()}
    data_since = min(first_day.values())

    # --- Daily rows: DAU, new users, cumulative, peak concurrent ---
    active_by_day: dict[date, set[int]] = defaultdict(set)
    for user_id, days in user_days.items():
        for d in days:
            active_by_day[d].add(user_id)
    new_by_day: dict[date, int] = defaultdict(int)
    for u, d in first_day.items():
        new_by_day[d] += 1

    daily: list[DailyRow] = []
    seen_users: set[int] = set()
    d = data_since
    one = timedelta(days=1)
    while d <= today:
        active = active_by_day.get(d, set())
        seen_users |= active
        daily.append(
            DailyRow(
                day=d,
                dau=len(active),
                new_users=new_by_day.get(d, 0),
                cumulative_users=len(seen_users),
                peak_concurrent=_peak_concurrent(day_intervals.get(d, [])),
            )
        )
        d += one

    # --- Trailing-window actives ---
    def _actives_in_window(days_back: int) -> int:
        start = today - timedelta(days=days_back - 1)
        users: set[int] = set()
        for day, us in active_by_day.items():
            if start <= day <= today:
                users |= us
        return len(users)

    # --- Retention by cohort (first active day) ---
    cohorts_users: dict[date, list[int]] = defaultdict(list)
    for u, d0 in first_day.items():
        cohorts_users[d0].append(u)

    cohorts: list[CohortRow] = []
    d1_num = d1_den = d7_num = d7_den = 0
    for cohort_day in sorted(cohorts_users):
        members = cohorts_users[cohort_day]
        row = CohortRow(cohort_day=cohort_day, size=len(members))
        # D+1 measurable only once cohort_day+1 has fully elapsed (<= today).
        if cohort_day + timedelta(days=1) <= today:
            target = cohort_day + timedelta(days=1)
            ret = sum(1 for u in members if target in user_days[u])
            row.d1_retained = ret
            row.d1_rate = ret / len(members) if members else None
            d1_num += ret
            d1_den += len(members)
        if cohort_day + timedelta(days=7) <= today:
            target = cohort_day + timedelta(days=7)
            ret = sum(1 for u in members if target in user_days[u])
            row.d7_retained = ret
            row.d7_retained_rate = ret / len(members) if members else None
            d7_num += ret
            d7_den += len(members)
        cohorts.append(row)

    return UsageStats(
        generated_at=datetime.now(_UTC),
        timezone="Asia/Seoul (KST, UTC+9)",
        data_since=data_since,
        today=today,
        total_users=len(user_days),
        dau_today=len(active_by_day.get(today, set())),
        wau=_actives_in_window(7),
        mau=_actives_in_window(30),
        overall_d1_rate=(d1_num / d1_den) if d1_den else None,
        overall_d7_rate=(d7_num / d7_den) if d7_den else None,
        daily=daily,
        cohorts=cohorts,
    )
