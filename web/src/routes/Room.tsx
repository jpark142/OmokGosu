import { useEffect, useMemo, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { useRoomSocket } from "@/hooks/useRoomSocket";
import { leaveRoom } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RoomMemberSummary } from "@/types/protocol";

function MemberCard({
  label,
  member,
  ready,
  isYou,
}: {
  label: string;
  member: RoomMemberSummary | null;
  ready: boolean;
  isYou: boolean;
}) {
  return (
    <div className="bg-white rounded-md border border-stone-200 p-4 min-h-[120px] flex flex-col">
      <div className="text-xs uppercase text-stone-500 mb-1">{label}</div>
      {member === null ? (
        <div className="flex-1 flex items-center justify-center text-stone-400">
          (대기 중)
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <div className="font-semibold text-lg">{member.username}</div>
            {isYou && <span className="text-xs px-1.5 py-0.5 bg-stone-200 rounded">나</span>}
          </div>
          <div className="text-sm text-stone-500 mt-1">
            <span className="text-green-600">{member.wins}승</span>
            {" · "}
            <span className="text-red-600">{member.losses}패</span>
            {member.wins + member.losses > 0 && (
              <> · 승률 {Math.round((member.wins / (member.wins + member.losses)) * 100)}%</>
            )}
          </div>
          <div className="mt-auto pt-2">
            {ready ? (
              <span className="inline-block text-xs px-2 py-0.5 bg-green-100 text-green-800 rounded">
                READY
              </span>
            ) : (
              <span className="inline-block text-xs px-2 py-0.5 bg-stone-100 text-stone-500 rounded">
                대기
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function Room() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { room, connected, gameId, closed, send } = useRoomSocket(roomId);

  // Auto-navigate to game when host starts.
  useEffect(() => {
    if (gameId !== null) navigate(`/game/${gameId}`);
  }, [gameId, navigate]);

  // Room closed (host left) → kick to lobby.
  useEffect(() => {
    if (closed !== null) {
      toast.info(closed.reason === "host_left" ? "방장이 떠났습니다" : "방이 종료되었습니다");
      navigate("/lobby", { replace: true });
    }
  }, [closed, navigate]);

  const me = user;
  const isHost = useMemo(
    () => (me && room ? me.id === room.host.user_id : false),
    [me, room],
  );
  const isGuest = useMemo(
    () => (me && room?.guest ? me.id === room.guest.user_id : false),
    [me, room],
  );

  const onReady = () => {
    if (!room || !isGuest) return;
    send({ type: "ready", value: !room.guest_ready });
  };

  const onStart = () => {
    if (!room || !isHost) return;
    if (!room.guest || !room.guest_ready) {
      toast.error("게스트가 Ready 상태여야 시작할 수 있습니다");
      return;
    }
    send({ type: "start" });
  };

  // Track whether the user is intentionally leaving (button or beforeunload)
  // so the unmount-only cleanup (Game-start navigation) doesn't fire a leave.
  const intentionalLeave = useRef(false);

  const onLeave = async () => {
    intentionalLeave.current = true;
    if (!roomId) return;
    try {
      await leaveRoom(roomId);
    } catch (e) {
      console.error("leave failed", e);
    }
    navigate("/lobby");
  };

  // (Tab-close cleanup is centralized in AuthProvider via /api/rooms/leave-all
  //  so the host quitting from anywhere — Room, Game, Lobby — deletes the
  //  room they own. No per-screen beforeunload needed here.)

  return (
    <div className="min-h-screen p-4 md:p-8 bg-stone-50">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate("/lobby")}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 로비
          </button>
          <div className="text-xs text-stone-500">
            {connected ? "연결됨" : "연결 중..."} · {roomId}
          </div>
        </div>

        {/* Title */}
        <div className="bg-white rounded-md border border-stone-200 p-4">
          <div className="text-xs text-stone-500 mb-1">방 제목</div>
          <div className="text-xl font-bold">{room?.title ?? "—"}</div>
          {room?.has_password && (
            <div className="text-xs text-stone-400 mt-1">🔒 비공개 방</div>
          )}
        </div>

        {/* Members */}
        <div className="grid grid-cols-2 gap-3">
          <MemberCard
            label="방장"
            member={room?.host ?? null}
            ready={true /* host is implicitly ready */}
            isYou={isHost}
          />
          <MemberCard
            label="게스트"
            member={room?.guest ?? null}
            ready={room?.guest_ready ?? false}
            isYou={isGuest}
          />
        </div>

        {/* Actions */}
        <div className="space-y-2">
          {isGuest && (
            <button
              onClick={onReady}
              className={`w-full py-3 rounded font-medium ${
                room?.guest_ready
                  ? "bg-stone-200 text-stone-700 hover:bg-stone-300"
                  : "bg-green-600 text-white hover:bg-green-700"
              }`}
            >
              {room?.guest_ready ? "Ready 취소" : "Ready"}
            </button>
          )}
          {isHost && (
            <button
              onClick={onStart}
              disabled={!room?.guest || !room?.guest_ready}
              className="w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800 disabled:bg-stone-300"
            >
              게임 시작
            </button>
          )}
          <button
            onClick={onLeave}
            className="w-full py-2 border border-red-300 text-red-600 rounded hover:bg-red-50"
          >
            방 나가기
          </button>
        </div>

        {!isHost && !isGuest && room && (
          <div className="text-xs text-center text-stone-500">
            이 방의 멤버가 아닙니다.
          </div>
        )}
      </div>
    </div>
  );
}
