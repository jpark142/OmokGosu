"""Auth REST endpoints: register, login, me.

Token: HS256 JWT, sub=user_id, 7-day TTL. Issued only by `/login` (and indirectly
by `/register` for convenience so the client can drop the user straight into the
app). Passwords are hashed with bcrypt.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.auth.security import create_access_token, hash_password, verify_password
from omok_server.db.models import User
from omok_server.schemas import AuthCredentials, AuthResponse, UserSummary

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_summary(u: User, current_room_id: str | None = None) -> UserSummary:
    return UserSummary(
        id=u.id,
        username=u.username,
        wins=u.wins,
        losses=u.losses,
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
    existing = session.exec(select(User).where(User.username == body.username)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already taken")
    user = User(username=body.username, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthResponse(
        access_token=create_access_token(user.id, token_version=user.token_version),
        user=_summary_with_room(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: AuthCredentials,
    session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    user = session.exec(select(User).where(User.username == body.username)).first()
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
    """Stateless JWT — there's no server-side session to invalidate. The point
    of this endpoint is to leave all rooms the user is currently in so logging
    out also deletes any room they host."""
    from omok_server.api.rooms import leave_all_rooms_for_user

    await leave_all_rooms_for_user(user.id, db=session)
