"""Auth REST endpoints: register, login, me.

Token: HS256 JWT, sub=user_id, 7-day TTL. Issued only by `/login` (and indirectly
by `/register` for convenience so the client can drop the user straight into the
app). Passwords are hashed with bcrypt.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.auth.security import create_access_token, hash_password, verify_password
from omok_server.auth.username_rules import UsernameError, validate_username
from omok_server.db.models import User
from omok_server.schemas import AuthCredentials, AuthResponse, UserSummary
from omok_server.ws.registry import registry as ws_registry

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_summary(u: User, current_room_id: str | None = None) -> UserSummary:
    return UserSummary(
        id=u.id,
        username=u.username,
        wins=u.wins,
        losses=u.losses,
        draws=u.draws,
        current_room_id=current_room_id,
    )


def _summary_with_room(u: User) -> UserSummary:
    from omok_server.game.room_manager import room_manager
    return _to_summary(u, current_room_id=room_manager.find_room_for_user(u.id))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: AuthCredentials,
    session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    try:
        username = validate_username(body.username)
    except UsernameError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Case-insensitive uniqueness: "Apple" and "apple" must not coexist, so a
    # new name can't impersonate an existing one by case alone. (Hangul has no
    # case, so this only affects Latin names.)
    existing = session.exec(
        select(User).where(func.lower(User.username) == username.lower())
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already taken")
    user = User(username=username, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthResponse(
        access_token=create_access_token(user.id, token_version=user.token_version),
        user=_summary_with_room(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: AuthCredentials,
    session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    # Match the username case-insensitively (registration now enforces
    # case-insensitive uniqueness). If legacy case-collisions exist, prefer an
    # exact-case match so each side can still log into its own account.
    typed = (body.username or "").strip()
    candidates = session.exec(
        select(User).where(func.lower(User.username) == typed.lower())
    ).all()
    user = next((u for u in candidates if u.username == typed), candidates[0] if candidates else None)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password"
        )
    # Bump first so the issued token is the *only* valid one going forward —
    # any token previously held by this user (in another tab/device) will
    # fail the ver check on its next request.
    user.token_version += 1
    session.add(user)
    session.commit()
    session.refresh(user)
    # Close any WS that the previous token still holds open across all 3
    # channels (lobby / room / game) so the displaced session disconnects
    # immediately instead of waiting for its next inbound message.
    await ws_registry.close_all(user.id, code=4401)
    return AuthResponse(
        access_token=create_access_token(user.id, token_version=user.token_version),
        user=_summary_with_room(user),
    )


@router.get("/me", response_model=UserSummary)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserSummary:
    return _summary_with_room(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Stateless JWT — there's no server-side session to invalidate. We do
    two cleanup steps so the user actually disappears from peer-facing UI:
    leave any rooms they're hosting/joining, and force-close every open WS
    they own so the lobby presence panel reflects them as offline right
    away (without waiting for the client to tear down its own sockets)."""
    from omok_server.api.rooms import leave_all_rooms_for_user

    await leave_all_rooms_for_user(user.id, db=session)
    await ws_registry.close_all(user.id, code=4401)
