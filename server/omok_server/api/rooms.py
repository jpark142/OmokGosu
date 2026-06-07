"""Room REST: list / create / join / leave.

Ready/start are WS-only (instant push to both members). REST handles the
lobby-level discovery and the "I'm coming into this room" handshake.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.db.models import User
from omok_server.game.room import Room
from omok_server.game.room_manager import room_manager
from omok_server.schemas import (
    CreateRoomReq,
    JoinRoomReq,
    RoomDetail,
    RoomMemberSummary,
    RoomStatusStr,
    RoomSummary,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def _member_for(user_id: int, session: Session) -> RoomMemberSummary | None:
    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        return None
    return RoomMemberSummary(
        user_id=user.id, username=user.username,
        wins=user.wins, losses=user.losses, draws=user.draws,
    )


def room_to_summary(room: Room, session: Session) -> RoomSummary:
    host = _member_for(room.host_user_id, session)
    if host is None:
        # Host vanished from DB — shouldn't happen but treat as anonymous placeholder.
        host = RoomMemberSummary(
            user_id=room.host_user_id, username="?", wins=0, losses=0, draws=0,
        )
    guest = _member_for(room.guest_user_id, session) if room.guest_user_id is not None else None
    return RoomSummary(
        room_id=room.room_id,
        title=room.title,
        has_password=room.password_hash is not None,
        host=host,
        guest=guest,
        status=RoomStatusStr(room.status.value),
        created_at=room.created_at,
        current_game_id=room.current_game_id,
    )


def room_to_detail(room: Room, session: Session) -> RoomDetail:
    summary = room_to_summary(room, session)
    return RoomDetail(
        **summary.model_dump(),
        guest_ready=room.guest_ready,
        games_played=room.games_played,
    )


@router.get("", response_model=list[RoomSummary])
def list_rooms(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RoomSummary]:
    return [room_to_summary(r, session) for r in room_manager.list()]


@router.post("", response_model=RoomDetail, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: CreateRoomReq,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RoomDetail:
    password = body.password if body.password else None
    room = await room_manager.create(title=body.title, host_user_id=user.id, password=password)
    detail = room_to_detail(room, session)
    # Lobby push so other clients see the new room without polling.
    summary = room_to_summary(room, session)
    await room_manager.broadcast_lobby(
        {"type": "lobby_update", "action": "created", "room_id": room.room_id, "room": summary.model_dump()}
    )
    return detail


@router.get("/{room_id}", response_model=RoomDetail)
def get_room(
    room_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RoomDetail:
    room = room_manager.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    if not room.is_member(user.id):
        raise HTTPException(status_code=403, detail="not a member of this room")
    return room_to_detail(room, session)


@router.post("/{room_id}/join", response_model=RoomDetail)
async def join_room(
    room_id: str,
    body: JoinRoomReq,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RoomDetail:
    room, err = await room_manager.join(room_id, user_id=user.id, password=body.password)
    if err == "not_found" or room is None:
        raise HTTPException(status_code=404, detail="room not found")
    if err == "full":
        raise HTTPException(status_code=409, detail="room is full")
    if err == "wrong_password":
        raise HTTPException(status_code=401, detail="wrong password")
    if err == "in_progress":
        raise HTTPException(status_code=409, detail="game in progress")
    is_new_guest = err is None  # "already_in" means host re-entering, no message
    if err == "already_in":
        pass
    detail = room_to_detail(room, session)
    # Push room state to existing members; push lobby update so list shows new guest.
    await room_manager.broadcast_room(room.room_id, {"type": "room_state", "room": detail.model_dump()})
    await room_manager.broadcast_lobby(
        {"type": "lobby_update", "action": "updated", "room_id": room.room_id,
         "room": room_to_summary(room, session).model_dump()}
    )
    if is_new_guest:
        from omok_server.api import chat as chat_helpers
        await chat_helpers.emit_system_message(
            key=f"room:{room.room_id}",
            text=f"{user.username} 님이 입장했습니다.",
            broadcast=lambda p: room_manager.broadcast_room(room.room_id, p),
        )
    return detail


async def leave_one_room(room_id: str, *, user_id: int, db: Session) -> None:
    """Process a single user leaving a single room + broadcast resulting state.

    Idempotent — calling with a user_id that's not a member is a no-op.
    Used both by the explicit Leave button (REST + WS) and by the bulk
    `leave_all_rooms_for_user` cleanup.
    """
    from omok_server.api import chat as chat_helpers

    # Resolve the leaver's name before the room mutates so the system message
    # has the right username even if the user row gets deleted later.
    leaver = db.get(User, user_id)
    leaver_name = leaver.username if leaver is not None else "(unknown)"

    _, host_left = await room_manager.leave(room_id, user_id=user_id)
    if host_left:
        # Room is gone — drop its chat buffer too so it doesn't outlive the
        # room in memory.
        chat_helpers.drop_channel(f"room:{room_id}")
        await room_manager.broadcast_room(room_id, {"type": "room_closed", "reason": "host_left"})
        await room_manager.broadcast_lobby(
            {"type": "lobby_update", "action": "removed", "room_id": room_id, "room": None}
        )
        return
    refreshed = room_manager.get(room_id)
    if refreshed is None:
        return
    await room_manager.broadcast_room(
        room_id, {"type": "room_state", "room": room_to_detail(refreshed, db).model_dump()}
    )
    await room_manager.broadcast_lobby(
        {"type": "lobby_update", "action": "updated", "room_id": room_id,
         "room": room_to_summary(refreshed, db).model_dump()}
    )
    # Guest left (host stayed) — note it in the room chat for the host.
    await chat_helpers.emit_system_message(
        key=f"room:{room_id}",
        text=f"{leaver_name} 님이 퇴장했습니다.",
        broadcast=lambda p: room_manager.broadcast_room(room_id, p),
    )


async def leave_all_rooms_for_user(user_id: int, *, db: Session) -> int:
    """Best-effort cleanup: leave every room the user is a member of.

    Used by /api/rooms/leave-all (beforeunload) and /api/auth/logout. Returns
    the number of rooms touched (for logging / tests).
    """
    count = 0
    for room in list(room_manager.list()):
        if room.host_user_id == user_id or room.guest_user_id == user_id:
            await leave_one_room(room.room_id, user_id=user_id, db=db)
            count += 1
    return count


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    room_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    await leave_one_room(room_id, user_id=user.id, db=session)


@router.post("/leave-all", status_code=status.HTTP_204_NO_CONTENT)
async def leave_all(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Drop the caller from every room they're in. Designed for fire-and-forget
    use via `fetch(..., {keepalive: true})` on beforeunload — both as host
    (room is deleted) and as guest (slot is cleared)."""
    await leave_all_rooms_for_user(user.id, db=session)
