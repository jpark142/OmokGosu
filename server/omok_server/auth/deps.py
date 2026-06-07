"""FastAPI dependencies for auth.

Two flavors:
  - `get_current_user`: HTTP routes, reads `Authorization: Bearer <token>` header.
  - `get_current_user_ws`: WS handler helper, takes the websocket and validates
    its `?token=` query param. Returns the User or closes the socket.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from starlette.websockets import WebSocket

from omok_server.auth.security import TokenError, decode_access_token
from omok_server.db.engine import engine
from omok_server.db.models import User

# tokenUrl is used by Swagger UI for the "Authorize" button.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db_session() -> Session:
    """FastAPI dependency: yields a SQLModel session and closes it afterwards."""
    with Session(engine) as session:
        yield session


def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
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
    user = session.exec(select(User).where(User.id == payload.user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if user.token_version != payload.ver:
        # Some newer token has been issued for this user — most likely a
        # second login from another browser/device. Treat the old one as
        # logged out. The frontend reads this detail to surface a clearer
        # toast than the generic "expired" message.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session displaced",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def verify_ws_client_version(ws: WebSocket) -> bool:
    """Validate `?client_version=` on a WebSocket handshake.

    Returns True if compatible (or version unspecified — lenient, matching the
    HTTP middleware policy). Returns False after closing the socket with
    close code 4426 if the version is too old.

    Call this *after* ws.accept() in each /ws/* handler.
    """
    from omok_server.version import is_client_compatible
    client_version = ws.query_params.get("client_version")
    if is_client_compatible(client_version):
        return True
    await ws.close(code=4426)
    return False


async def get_current_user_ws(ws: WebSocket) -> User | None:
    """Validate ?token=... on a WebSocket. Returns User or None (after closing)."""
    token = ws.query_params.get("token", "")
    try:
        payload = decode_access_token(token)
    except TokenError:
        # Custom close code 4401 = "unauthorized"; WebSocket spec reserves 4000-4999 for app use.
        await ws.close(code=4401)
        return None
    with Session(engine) as session:
        user = session.exec(select(User).where(User.id == payload.user_id)).first()
    if user is None:
        await ws.close(code=4401)
        return None
    if user.token_version != payload.ver:
        # Another login has retired this token. The frontend's WS hooks
        # treat 4401 as terminal (no reconnect), and the next REST call
        # will dispatch omok:unauthorized which redirects to /login.
        await ws.close(code=4401)
        return None
    return user
