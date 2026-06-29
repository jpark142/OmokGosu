"""System-level read endpoints: health probe + version advertisement.

`/api/version` is the source of truth that the frontend polls every 60s to
decide whether a soft banner or hard modal should be shown.

`/api/health` is the cheap liveness probe Fly.io (and any other orchestrator)
hits — it must stay dependency-free (no DB, no auth) so a failing dependency
doesn't take the whole pod down via the health check.
"""
import os

from fastapi import APIRouter
from pydantic import BaseModel

from omok_server.services.operators import operator_usernames
from omok_server.version import MIN_CLIENT_VERSION, SERVER_VERSION

router = APIRouter(prefix="/api", tags=["system"])


def _is_dev_mode() -> bool:
    """Gates a few owner-only debug affordances (e.g. the in-game
    "clip clock to 10s" cheat). Set OMOK_DEV_MODE=1 in the env to enable;
    unset on prod once you're done verifying."""
    return os.environ.get("OMOK_DEV_MODE", "").strip() == "1"


class VersionInfo(BaseModel):
    version: str
    min_client_version: str
    # Reflected to the client so it can conditionally render dev-only
    # affordances (the Game.tsx "DEV: 시계 단축" button). Not auth — the
    # gate that matters lives on the cheat endpoint itself.
    dev_mode: bool


class HealthInfo(BaseModel):
    status: str
    version: str


class OperatorsInfo(BaseModel):
    # Operator usernames, in display form. Public on purpose — the badge is
    # meant to be visible, so there's nothing secret about who the operators
    # are. The client compares case-insensitively when rendering the badge.
    usernames: list[str]


@router.get("/version", response_model=VersionInfo)
def version() -> VersionInfo:
    """No auth — clients poll this before any other request."""
    return VersionInfo(
        version=SERVER_VERSION,
        min_client_version=MIN_CLIENT_VERSION,
        dev_mode=_is_dev_mode(),
    )


@router.get("/operators", response_model=OperatorsInfo)
def operators() -> OperatorsInfo:
    """No auth — the operator badge is public info the client renders for
    every visible username."""
    return OperatorsInfo(usernames=operator_usernames())


@router.get("/health", response_model=HealthInfo)
def health() -> HealthInfo:
    """Liveness probe. Returns 200 as long as the process can serve requests
    — intentionally does not touch the DB or any external dependency so a
    transient SQLite hiccup doesn't make Fly cycle the machine."""
    return HealthInfo(status="ok", version=SERVER_VERSION)
