"""System-level read endpoints: health probe + version advertisement.

`/api/version` is the source of truth that the frontend polls every 60s to
decide whether a soft banner or hard modal should be shown.

`/api/health` is the cheap liveness probe Fly.io (and any other orchestrator)
hits — it must stay dependency-free (no DB, no auth) so a failing dependency
doesn't take the whole pod down via the health check.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from omok_server.version import MIN_CLIENT_VERSION, SERVER_VERSION

router = APIRouter(prefix="/api", tags=["system"])


class VersionInfo(BaseModel):
    version: str
    min_client_version: str


class HealthInfo(BaseModel):
    status: str
    version: str


@router.get("/version", response_model=VersionInfo)
def version() -> VersionInfo:
    """No auth — clients poll this before any other request."""
    return VersionInfo(version=SERVER_VERSION, min_client_version=MIN_CLIENT_VERSION)


@router.get("/health", response_model=HealthInfo)
def health() -> HealthInfo:
    """Liveness probe. Returns 200 as long as the process can serve requests
    — intentionally does not touch the DB or any external dependency so a
    transient SQLite hiccup doesn't make Fly cycle the machine."""
    return HealthInfo(status="ok", version=SERVER_VERSION)
