import UserHoverCard from "@/components/UserHoverCard";
import type { RoomSummary } from "@/types/protocol";

interface Props {
  room: RoomSummary;
  currentUserId: number | undefined;
  onJoin: (room: RoomSummary) => void;
  onEnter: (room: RoomSummary) => void;
  onSpectate: (gameId: string) => void;
}

export default function RoomCard({ room, currentUserId, onJoin, onEnter, onSpectate }: Props) {
  const youHost = currentUserId !== undefined && currentUserId === room.host.user_id;
  const youGuest =
    currentUserId !== undefined && room.guest !== null && currentUserId === room.guest.user_id;
  const youAreIn = youHost || youGuest;
  const full = room.guest !== null;
  const playing = room.status === "PLAYING";
  const canJoin = !youAreIn && !full && !playing;

  const statusBadge = playing ? "게임 중" : full ? "꽉 참" : "대기 중";
  const statusClass = playing
    ? "bg-amber-100 text-amber-800"
    : full
      ? "bg-stone-200 text-stone-600"
      : "bg-green-100 text-green-800";

  return (
    <div
      className={`bg-white rounded-md border p-5 h-full min-h-[7rem] flex justify-between items-center ${
        youAreIn ? "border-amber-400 bg-amber-50/50" : "border-stone-200"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {room.has_password && <span className="text-stone-400 text-sm">🔒</span>}
          <div className="font-medium truncate">{room.title}</div>
          {youHost && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-200 text-amber-900 rounded">
              내가 방장
            </span>
          )}
          {youGuest && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-200 text-amber-900 rounded">
              참여 중
            </span>
          )}
        </div>
        <div className="text-xs text-stone-500">
          <UserHoverCard userId={room.host.user_id}>{room.host.username}</UserHoverCard>
          {" "}
          ({room.host.wins}승{(room.host.draws ?? 0) > 0 && ` ${room.host.draws}무`} {room.host.losses}패)
          {room.guest && (
            <>
              {" vs "}
              <UserHoverCard userId={room.guest.user_id}>{room.guest.username}</UserHoverCard>
              {" "}
              ({room.guest.wins}승{(room.guest.draws ?? 0) > 0 && ` ${room.guest.draws}무`} {room.guest.losses}패)
            </>
          )}
        </div>
      </div>
      <div className="flex flex-col items-end gap-2 ml-3">
        <span className={`text-xs px-2 py-0.5 rounded ${statusClass}`}>{statusBadge}</span>
        {youAreIn ? (
          <button
            onClick={() => onEnter(room)}
            className="text-sm px-3 py-1 bg-amber-500 text-white rounded hover:bg-amber-600"
          >
            이어서
          </button>
        ) : playing && room.current_game_id ? (
          <button
            onClick={() => onSpectate(room.current_game_id!)}
            className="text-sm px-3 py-1 bg-sky-600 text-white rounded hover:bg-sky-700"
          >
            관전하기
          </button>
        ) : (
          <button
            onClick={() => onJoin(room)}
            disabled={!canJoin}
            className="text-sm px-3 py-1 bg-stone-900 text-white rounded hover:bg-stone-800 disabled:bg-stone-300"
          >
            입장
          </button>
        )}
      </div>
    </div>
  );
}
