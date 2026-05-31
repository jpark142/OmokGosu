import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import AIPlayDialog from "@/components/AIPlayDialog";
import CreateRoomDialog from "@/components/CreateRoomDialog";
import RoomCard from "@/components/RoomCard";
import { useLobbySocket } from "@/hooks/useLobbySocket";
import { createGame, createRoom, joinRoom } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { HttpError } from "@/lib/fetcher";
import type {
  AIDifficulty,
  AILevel,
  RoomSummary,
} from "@/types/protocol";

export default function Lobby() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { rooms, connected } = useLobbySocket();
  const [createOpen, setCreateOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const winRate =
    user && user.wins + user.losses > 0
      ? `${Math.round((user.wins / (user.wins + user.losses)) * 100)}%`
      : "—";

  const onCreate = async (title: string, password: string) => {
    setBusy(true);
    try {
      const room = await createRoom({ title, password: password || null });
      setCreateOpen(false);
      navigate(`/rooms/${room.room_id}`);
    } catch (e) {
      toast.error((e as Error).message || "방 생성 실패");
    } finally {
      setBusy(false);
    }
  };

  const onJoin = async (room: RoomSummary) => {
    let password: string | null = null;
    if (room.has_password) {
      const v = window.prompt(`비밀번호 (${room.title}):`);
      if (v === null) return;
      password = v;
    }
    setBusy(true);
    try {
      await joinRoom(room.room_id, { password });
      navigate(`/rooms/${room.room_id}`);
    } catch (e) {
      if (e instanceof HttpError) {
        if (e.status === 401) toast.error("비밀번호가 틀렸습니다");
        else if (e.status === 409) toast.error("이미 진행 중이거나 꽉 찬 방입니다");
        else toast.error("입장 실패");
      } else {
        toast.error("입장 실패");
      }
    } finally {
      setBusy(false);
    }
  };

  // For rooms the user is already in (host or guest): skip the join REST call
  // and navigate straight to the room. Calling /join as the host returns
  // "already_in" which works, but going direct avoids confusing the server-side
  // broadcasts and is faster.
  const onEnter = (room: RoomSummary) => {
    navigate(`/rooms/${room.room_id}`);
  };

  const onAIStart = async (level: AILevel, difficulty: AIDifficulty | undefined) => {
    setBusy(true);
    try {
      const res = await createGame({
        mode: "hva",
        ai_level: level,
        ai_difficulty: difficulty,
      });
      setAiOpen(false);
      navigate(`/game/${res.game_id}`);
    } catch (e) {
      toast.error("AI 게임 생성 실패");
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  const visibleRooms = [...rooms].sort((a, b) => b.created_at - a.created_at);

  return (
    <div className="min-h-screen p-4 md:p-6 bg-stone-50">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-stone-900">로비</h1>
            <p className="text-xs text-stone-500">
              {connected ? "연결됨" : "연결 중..."} · 방 {rooms.length}개
            </p>
          </div>
          {user && (
            <div className="flex items-center gap-4">
              <div className="text-right text-sm">
                <div className="font-medium">{user.username}</div>
                <div className="text-xs text-stone-500">
                  <span className="text-green-600">{user.wins}승</span>
                  {" · "}
                  <span className="text-red-600">{user.losses}패</span>
                  {" · "}
                  승률 {winRate}
                </div>
              </div>
              <button
                onClick={logout}
                className="text-xs text-stone-500 hover:text-stone-900"
              >
                로그아웃
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setCreateOpen(true)}
            className="py-3 bg-amber-500 text-white rounded font-medium hover:bg-amber-600"
          >
            + 방 만들기
          </button>
          <button
            onClick={() => setAiOpen(true)}
            className="py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800"
          >
            AI와 두기
          </button>
        </div>

        {/* Room list */}
        <div className="space-y-2">
          {visibleRooms.length === 0 ? (
            <div className="bg-white rounded-md border border-dashed border-stone-300 p-8 text-center text-stone-500">
              아직 방이 없습니다. 첫 번째 방을 만들어 보세요.
            </div>
          ) : (
            visibleRooms.map((r) => (
              <RoomCard
                key={r.room_id}
                room={r}
                currentUserId={user?.id}
                onJoin={onJoin}
                onEnter={onEnter}
              />
            ))
          )}
        </div>

        <div className="text-xs text-stone-500 text-center border-t pt-4">
          렌주는 흑에게 3-3 / 4-4 / 장목 금수가 적용됩니다. 색은 게임 시작 시 무작위로 배정됩니다.
        </div>
      </div>

      <CreateRoomDialog
        open={createOpen}
        busy={busy}
        onClose={() => setCreateOpen(false)}
        onCreate={onCreate}
      />
      <AIPlayDialog
        open={aiOpen}
        busy={busy}
        onClose={() => setAiOpen(false)}
        onStart={onAIStart}
      />
    </div>
  );
}
