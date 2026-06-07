import { useEffect, useMemo, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import Chat from "@/components/Chat";
import UserHoverCard from "@/components/UserHoverCard";
import { useRoomSocket } from "@/hooks/useRoomSocket";
import { leaveRoom } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RoomMemberSummary } from "@/types/protocol";

function MemberCard({
  label,
  member,
  ready,
  isYou,
  canKick,
  onKick,
}: {
  label: string;
  member: RoomMemberSummary | null;
  ready: boolean;
  isYou: boolean;
  canKick?: boolean;            // true → render the "강퇴" button
  onKick?: () => void;
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
            <div className="font-semibold text-lg">
              <UserHoverCard userId={member.user_id}>{member.username}</UserHoverCard>
            </div>
            {isYou && <span className="text-xs px-1.5 py-0.5 bg-stone-200 rounded">나</span>}
          </div>
          <div className="text-sm text-stone-500 mt-1">
            <span className="text-green-600">{member.wins}승</span>
            {(member.draws ?? 0) > 0 && (
              <>
                {" · "}
                <span className="text-stone-500">{member.draws}무</span>
              </>
            )}
            {" · "}
            <span className="text-red-600">{member.losses}패</span>
            {member.wins + member.losses > 0 && (
              <> · 승률 {Math.round((member.wins / (member.wins + member.losses)) * 100)}%</>
            )}
          </div>
          <div className="mt-auto pt-2 flex items-center justify-between gap-2">
            {ready ? (
              <span className="inline-block text-xs px-2 py-0.5 bg-green-100 text-green-800 rounded">
                READY
              </span>
            ) : (
              <span className="inline-block text-xs px-2 py-0.5 bg-stone-100 text-stone-500 rounded">
                대기
              </span>
            )}
            {canKick && onKick && (
              <button
                onClick={onKick}
                className="text-xs px-2 py-1 border border-red-300 text-red-600 rounded hover:bg-red-50"
                title="이 게스트를 강퇴합니다"
              >
                강퇴
              </button>
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
  const { room, connected, gameId, closed, kickedUserId, chat, sendChat, send } =
    useRoomSocket(roomId);

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

  // "kicked" is broadcast to every socket in the room — only show the modal
  // when the targeted user_id is us.
  const wasKicked = kickedUserId !== null && user?.id === kickedUserId;

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

  const onKickGuest = () => {
    if (!isHost || !room?.guest) return;
    if (!window.confirm(`${room.guest.username} 님을 강퇴하시겠습니까?`)) return;
    send({ type: "kick" });
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
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0">
              <div className="text-xs text-stone-500 mb-1">방 제목</div>
              <div className="text-xl font-bold truncate">{room?.title ?? "—"}</div>
              {room?.has_password && (
                <div className="text-xs text-stone-400 mt-1">🔒 비공개 방</div>
              )}
            </div>
            {room && room.games_played > 0 && (
              <div className="text-xs px-2 py-1 bg-stone-100 rounded text-stone-600 whitespace-nowrap">
                지금까지 {room.games_played}판
              </div>
            )}
          </div>
        </div>

        {/* Rematch banner: shown after the first completed game while waiting in LOBBY */}
        {room && room.games_played > 0 && room.status === "LOBBY" && (
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-900 text-center">
            방금 한 판 끝났습니다 — <strong>한 판 더?</strong>{" "}
            {isHost
              ? room.guest_ready
                ? "게스트가 준비 완료, 시작하세요."
                : "게스트의 준비를 기다리는 중..."
              : room?.guest_ready
                ? "방장이 시작할 때까지 대기 중..."
                : "Ready 버튼을 눌러 다시 시작하세요."}
          </div>
        )}

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
            canKick={isHost && !!room?.guest && room.status === "LOBBY"}
            onKick={onKickGuest}
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
              {room?.guest_ready
                ? "Ready 취소"
                : room && room.games_played > 0
                  ? "한 판 더 (Ready)"
                  : "Ready"}
            </button>
          )}
          {isHost && (
            <button
              onClick={onStart}
              disabled={!room?.guest || !room?.guest_ready}
              className="w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800 disabled:bg-stone-300"
            >
              {room && room.games_played > 0 ? "한 판 더 시작" : "게임 시작"}
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

        {/* Chat — visible to both members while waiting in the room */}
        <Chat
          title="방 채팅"
          messages={chat}
          onSend={sendChat}
          disabled={!connected}
          size="sm"
        />
      </div>

      {/* Kicked modal — only this user got removed by the host */}
      {wasKicked && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-40">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full space-y-4">
            <h2 className="text-lg font-bold">강퇴되었습니다</h2>
            <p className="text-sm text-stone-600">
              방장에 의해 강퇴되었습니다.
            </p>
            <button
              onClick={() => navigate("/lobby", { replace: true })}
              className="w-full py-2 bg-stone-900 text-white rounded hover:bg-stone-800"
            >
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
