"""ClientVersionGateMiddleware — refuse `/api/*` requests from outdated clients.

Policy:
  - `/api/version` itself is exempt (so a too-old client can still learn what
    version to upgrade to).
  - OPTIONS preflight is exempt (CORS).
  - Missing `X-Client-Version` header → pass (lenient for curl/debug/external).
  - Header present and below `MIN_CLIENT_VERSION` → 426 Upgrade Required.

The frontend's `lib/fetcher.ts` listens for 426 and dispatches the
`omok:upgrade-required` event so the global VersionProvider shows the hard
modal regardless of polling timing.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from omok_server.version import MIN_CLIENT_VERSION, SERVER_VERSION, is_client_compatible

_HEADER = "X-Client-Version"


class ClientVersionGateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Exempt: not /api/*, the version endpoint itself, OPTIONS preflight
        if not path.startswith("/api/") or path == "/api/version" or method == "OPTIONS":
            return await call_next(request)

        client_version = request.headers.get(_HEADER)
        if not is_client_compatible(client_version):
            return JSONResponse(
                status_code=426,
                content={
                    "detail": "client version too old",
                    "min_client_version": MIN_CLIENT_VERSION,
                    "server_version": SERVER_VERSION,
                },
                headers={"X-Min-Client-Version": MIN_CLIENT_VERSION},
            )

        return await call_next(request)
