"""System-level read endpoints: health probe + version advertisement.

`/api/version` is the source of truth that the frontend polls every 60s to
decide whether a soft banner or hard modal should be shown.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from omok_server.version import MIN_CLIENT_VERSION, SERVER_VERSION

router = APIRouter(prefix="/api", tags=["system"])


class VersionInfo(BaseModel):
    version: str
    min_client_version: str


@router.get("/version", response_model=VersionInfo)
def version() -> VersionInfo:
    """No auth — clients poll this before any other request."""
    return VersionInfo(version=SERVER_VERSION, min_client_version=MIN_CLIENT_VERSION)
