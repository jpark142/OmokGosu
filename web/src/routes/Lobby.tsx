import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import AIPlayDialog from "@/components/AIPlayDialog";
import Chat from "@/components/Chat";
import CreateRoomDialog from "@/components/CreateRoomDialog";
import OnlineUsersPanel from "@/components/OnlineUsersPanel";
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
  const { rooms, connected, chat, presence, sendChat } = useLobbySocket();
  const [createOpen, setCreateOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  // Win rate denominator counts only decisive games — draws are listed
  // separately in the strip below but don't influence the percentage.
  const winRate =
    user && user.wins + user.losses > 0
      ? `${Math.round((user.wins / (user.wins + user.losses)) * 100)}%`
      : "—";
  const userDraws = user?.draws ?? 0;

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

  // Jump directly into the game WS as a read-only viewer. RoomSummary now
  // carries current_game_id for PLAYING rooms so no extra REST call is needed.
  const onSpectate = (gameId: string) => {
    navigate(`/game/${gameId}`);
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

  const q = query.trim().toLowerCase();
  const visibleRooms = [...rooms]
    .filter((r) => q === "" || r.title.toLowerCase().includes(q))
    .sort((a, b) => b.created_at - a.created_at);

  // Client-side pagination: 4 rooms per page in a 2×2 grid. Rooms arrive over
  // the lobby WS in real time, so totalPages shifts as rooms open/close — we
  // clamp `page` to the valid range instead of letting it dangle out of bounds.
  const ROOMS_PER_PAGE = 4;
  const totalPages = Math.max(1, Math.ceil(visibleRooms.length / ROOMS_PER_PAGE));
  const safePage = Math.min(page, totalPages - 1);
  const pagedRooms = visibleRooms.slice(
    safePage * ROOMS_PER_PAGE,
    safePage * ROOMS_PER_PAGE + ROOMS_PER_PAGE,
  );

  return (
    <div className="min-h-screen p-4 md:p-6 bg-stone-50">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_18rem] gap-6">
        <div className="space-y-6 min-w-0">
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
                  {userDraws > 0 && (
                    <>
                      {" · "}
                      <span className="text-stone-500">{userDraws}무</span>
                    </>
                  )}
                  {" · "}
                  <span className="text-red-600">{user.losses}패</span>
                  {" · "}
                  승률 {winRate}
                </div>
              </div>
              <button
                onClick={() => navigate(`/users/${user.id}`)}
                className="text-xs text-stone-500 hover:text-stone-900"
                title="내 전적 + 기보"
              >
                🎯 내 전적
              </button>
              <button
                onClick={() => navigate("/leaderboard")}
                className="text-xs text-stone-500 hover:text-stone-900"
                title="전체 랭킹"
              >
                🏆 랭킹
              </button>
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

        {/* Search */}
        {rooms.length > 0 && (
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder="방 제목으로 검색..."
            className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
          />
        )}

        {/* Room list — 2×2 grid, 4 rooms/page */}
        {visibleRooms.length === 0 ? (
          <div className="bg-white rounded-md border border-dashed border-stone-300 p-8 text-center text-stone-500">
            {rooms.length === 0
              ? "아직 방이 없습니다. 첫 번째 방을 만들어 보세요."
              : `'${query}' 와 일치하는 방이 없습니다.`}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {pagedRooms.map((r) => (
                <RoomCard
                  key={r.room_id}
                  room={r}
                  currentUserId={user?.id}
                  onJoin={onJoin}
                  onEnter={onEnter}
                  onSpectate={onSpectate}
                />
              ))}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4">
                <button
                  onClick={() => setPage(Math.max(0, safePage - 1))}
                  disabled={safePage === 0}
                  className="px-3 py-1.5 text-sm border border-stone-300 rounded text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                >
                  ← 이전
                </button>
                <span className="text-sm text-stone-500 tabular-nums">
                  {safePage + 1} / {totalPages} 페이지
                  <span className="text-stone-400"> · 총 {visibleRooms.length}개</span>
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))}
                  disabled={safePage >= totalPages - 1}
                  className="px-3 py-1.5 text-sm border border-stone-300 rounded text-stone-700 hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                >
                  다음 →
                </button>
              </div>
            )}
          </div>
        )}

        {/* Lobby chat — visible to anyone in the lobby */}
        <Chat
          title="로비 채팅"
          messages={chat}
          onSend={sendChat}
          disabled={!connected}
          size="lg"
        />
        </div>

        {/* Right rail: live online users */}
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <OnlineUsersPanel users={presence} />
        </aside>
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
