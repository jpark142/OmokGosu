"""Operator-only admin endpoints.

Currently exposes usage analytics computed from SessionLog. Gated on the
operator list (same registry that drives the 운영자 badge) so only official
accounts can read it. The numbers stay private — the operator dashboard reads
this with the logged-in operator's JWT and can export a Markdown file
client-side; nothing is ever committed to the (public) repo.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from omok_server.auth.deps import _oauth2_scheme
from omok_server.auth.security import TokenError, decode_access_token
from omok_server.db.engine import engine
from omok_server.db.models import User
from omok_server.services import usage_stats
from omok_server.services.operators import is_operator
from sqlmodel import Session, select

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_operator(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
) -> None:
    """Gate a route to logged-in operator accounts.

    Raises 401 if the token is missing/invalid, 403 if a valid non-operator
    token is used. Returns nothing — it's a pure gate.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    with Session(engine) as db:
        user = db.exec(select(User).where(User.id == payload.user_id)).first()
    if user is None or user.token_version != payload.ver:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    if not is_operator(user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator only")


# --- Response models (mirror usage_stats dataclasses) ---

class DailyRowOut(BaseModel):
    day: str
    dau: int
    new_users: int
    cumulative_users: int
    peak_concurrent: int


class CohortRowOut(BaseModel):
    cohort_day: str
    size: int
    d1_retained: int | None
    d1_rate: float | None
    d7_retained: int | None
    d7_rate: float | None


class UsageStatsOut(BaseModel):
    generated_at: str
    timezone: str
    data_since: str | None
    today: str
    total_users: int
    dau_today: int
    wau: int
    mau: int
    overall_d1_rate: float | None
    overall_d7_rate: float | None
    daily: list[DailyRowOut]
    cohorts: list[CohortRowOut]


@router.get("/stats", response_model=UsageStatsOut, dependencies=[Depends(require_operator)])
def stats() -> UsageStatsOut:
    s = usage_stats.compute()
    return UsageStatsOut(
        generated_at=s.generated_at.isoformat(),
        timezone=s.timezone,
        data_since=s.data_since.isoformat() if s.data_since else None,
        today=s.today.isoformat(),
        total_users=s.total_users,
        dau_today=s.dau_today,
        wau=s.wau,
        mau=s.mau,
        overall_d1_rate=s.overall_d1_rate,
        overall_d7_rate=s.overall_d7_rate,
        daily=[
            DailyRowOut(
                day=r.day.isoformat(),
                dau=r.dau,
                new_users=r.new_users,
                cumulative_users=r.cumulative_users,
                peak_concurrent=r.peak_concurrent,
            )
            for r in s.daily
        ],
        cohorts=[
            CohortRowOut(
                cohort_day=r.cohort_day.isoformat(),
                size=r.size,
                d1_retained=r.d1_retained,
                d1_rate=r.d1_rate,
                d7_retained=r.d7_retained,
                d7_rate=r.d7_retained_rate,
            )
            for r in s.cohorts
        ],
    )
