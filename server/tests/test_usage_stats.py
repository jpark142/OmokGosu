"""Usage analytics: the usage_stats aggregation + the operator-gated endpoint.

compute() reads the whole SessionLog table, and the test DB is a single shared
temp file, so each test wipes SessionLog first and inserts rows with explicit
timestamps. user_id values are arbitrary — compute() never joins User, it only
buckets by the id in the log — so we don't bother creating real users here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from omok_server.db.engine import engine
from omok_server.db.models import SessionLog
from omok_server.services import usage_stats

from tests.conftest import unique_username

_UTC = timezone.utc


def _clear() -> None:
    with Session(engine) as db:
        for r in db.exec(select(SessionLog)).all():
            db.delete(r)
        db.commit()


def _add(user_id: int, connected_at: datetime, disconnected_at: datetime | None = None) -> None:
    with Session(engine) as db:
        db.add(
            SessionLog(
                user_id=user_id,
                connected_at=connected_at,
                disconnected_at=disconnected_at,
            )
        )
        db.commit()


def _utc(y: int, mo: int, d: int, h: int = 3, mi: int = 0) -> datetime:
    # 03:00 UTC = 12:00 KST same calendar day — keeps KST date == UTC date so
    # day math in tests is unsurprising (boundary cases get their own test).
    return datetime(y, mo, d, h, mi)


def test_empty_table_yields_zeroes() -> None:
    _clear()
    s = usage_stats.compute(now=_utc(2026, 6, 12, 13))
    assert s.total_users == 0
    assert s.daily == []
    assert s.cohorts == []
    assert s.overall_d1_rate is None
    assert s.overall_d7_rate is None
    assert s.data_since is None


def test_daily_dau_new_cumulative() -> None:
    _clear()
    # u1: active D0 only. u2: D0 and D1. u3: D2.
    _add(1, _utc(2026, 6, 10))
    _add(2, _utc(2026, 6, 10, 4))
    _add(2, _utc(2026, 6, 11))
    _add(3, _utc(2026, 6, 12))
    s = usage_stats.compute(now=_utc(2026, 6, 12, 13))

    assert s.total_users == 3
    assert s.data_since.isoformat() == "2026-06-10"
    assert s.today.isoformat() == "2026-06-12"
    assert s.dau_today == 1  # only u3 on June 12

    by_day = {r.day.isoformat(): r for r in s.daily}
    assert by_day["2026-06-10"].dau == 2
    assert by_day["2026-06-10"].new_users == 2
    assert by_day["2026-06-10"].cumulative_users == 2
    assert by_day["2026-06-11"].dau == 1
    assert by_day["2026-06-11"].new_users == 0
    assert by_day["2026-06-11"].cumulative_users == 2
    assert by_day["2026-06-12"].dau == 1
    assert by_day["2026-06-12"].new_users == 1
    assert by_day["2026-06-12"].cumulative_users == 3


def test_retention_d1_and_maturity() -> None:
    _clear()
    # Cohort June 10 = {u1, u2}; only u2 returns on June 11.
    _add(1, _utc(2026, 6, 10))
    _add(2, _utc(2026, 6, 10, 4))
    _add(2, _utc(2026, 6, 11))
    # u3 first-seen June 12 — its D+1 (June 13) hasn't elapsed yet at `now`.
    _add(3, _utc(2026, 6, 12))
    s = usage_stats.compute(now=_utc(2026, 6, 12, 13))

    cohorts = {c.cohort_day.isoformat(): c for c in s.cohorts}
    c10 = cohorts["2026-06-10"]
    assert c10.size == 2
    assert c10.d1_retained == 1
    assert abs(c10.d1_rate - 0.5) < 1e-9
    assert c10.d7_retained is None  # June 17 not reached → immature

    c12 = cohorts["2026-06-12"]
    assert c12.size == 1
    assert c12.d1_retained is None  # June 13 not reached → immature

    # Overall D+1 only averages mature cohorts (just June 10 here).
    assert abs(s.overall_d1_rate - 0.5) < 1e-9
    assert s.overall_d7_rate is None


def test_kst_day_boundary() -> None:
    _clear()
    # 15:30 UTC on June 1 == 00:30 KST on June 2 → must bucket as June 2 KST.
    _add(100, datetime(2026, 6, 1, 15, 30))
    s = usage_stats.compute(now=datetime(2026, 6, 2, 5, 0, tzinfo=_UTC))
    assert s.data_since.isoformat() == "2026-06-02"
    assert [r.day.isoformat() for r in s.daily] == ["2026-06-02"]
    assert s.daily[0].dau == 1


def test_peak_concurrent_counts_overlap() -> None:
    _clear()
    # Two sessions overlapping on June 10 → peak 2; a third, non-overlapping.
    _add(1, _utc(2026, 6, 10, 3), _utc(2026, 6, 10, 5))
    _add(2, _utc(2026, 6, 10, 4), _utc(2026, 6, 10, 6))   # overlaps u1 4-5
    _add(3, _utc(2026, 6, 10, 8), _utc(2026, 6, 10, 9))   # alone
    s = usage_stats.compute(now=_utc(2026, 6, 11))
    by_day = {r.day.isoformat(): r for r in s.daily}
    assert by_day["2026-06-10"].peak_concurrent == 2


# --- Endpoint gating ---


def test_stats_endpoint_requires_auth(client) -> None:
    r = client.get("/api/admin/stats")
    assert r.status_code == 401


def test_stats_endpoint_forbidden_for_non_operator(auth_client) -> None:
    api, _token, _user = auth_client
    r = api.get("/api/admin/stats")
    assert r.status_code == 403


def test_stats_endpoint_allows_operator(client) -> None:
    # Default operator username is "운영자" (operators._DEFAULT).
    r = client.post("/api/auth/register", json={"username": "운영자", "password": "pw1234"})
    # If a prior test already registered it, fall back to logging in.
    if r.status_code == 201:
        token = r.json()["access_token"]
    else:
        r = client.post("/api/auth/login", json={"username": "운영자", "password": "pw1234"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
    r = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "daily" in body and "cohorts" in body
    assert "overall_d1_rate" in body and "overall_d7_rate" in body
