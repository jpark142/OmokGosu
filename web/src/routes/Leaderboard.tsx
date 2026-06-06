// /leaderboard — global ranking by total wins.

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import UserHoverCard from "@/components/UserHoverCard";
import { getLeaderboard } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LeaderboardEntry } from "@/types/protocol";

function rankBadge(rank: number): { icon: string; color: string } {
  if (rank === 1) return { icon: "🥇", color: "text-amber-600" };
  if (rank === 2) return { icon: "🥈", color: "text-stone-500" };
  if (rank === 3) return { icon: "🥉", color: "text-orange-700" };
  return { icon: `${rank}`, color: "text-stone-500" };
}

export default function Leaderboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLeaderboard(50)
      .then((r) => {
        if (!cancelled) setEntries(r.entries);
      })
      .catch(() => {
        if (!cancelled) setError("불러오기 실패");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen p-4 md:p-6 bg-stone-50">
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate("/lobby")}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 로비
          </button>
          <h1 className="text-2xl font-bold">랭킹</h1>
          <span className="w-12" />
        </div>

        <div className="bg-white rounded-md border border-stone-200 overflow-hidden">
          {error && (
            <div className="p-6 text-center text-red-500 text-sm">{error}</div>
          )}
          {!error && entries === null && (
            <div className="p-6 text-center text-stone-400 text-sm">불러오는 중...</div>
          )}
          {!error && entries !== null && entries.length === 0 && (
            <div className="p-8 text-center text-stone-500 text-sm">
              아직 경기를 끝낸 사람이 없습니다.
            </div>
          )}
          {!error && entries !== null && entries.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-stone-500 text-xs">
                <tr>
                  <th className="px-4 py-2 text-left w-12">순위</th>
                  <th className="px-4 py-2 text-left">닉네임</th>
                  <th className="px-4 py-2 text-right w-16">승</th>
                  <th className="px-4 py-2 text-right w-16">패</th>
                  <th className="px-4 py-2 text-right w-16">승률</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => {
                  const total = e.wins + e.losses;
                  const winRate = total > 0 ? Math.round((e.wins / total) * 100) : 0;
                  const isMe = user?.id === e.user_id;
                  const badge = rankBadge(e.rank);
                  return (
                    <tr
                      key={e.user_id}
                      className={`border-t border-stone-100 ${
                        isMe ? "bg-amber-50" : "hover:bg-stone-50"
                      }`}
                    >
                      <td className={`px-4 py-2 font-bold ${badge.color}`}>
                        {badge.icon}
                      </td>
                      <td className="px-4 py-2">
                        <UserHoverCard userId={e.user_id}>
                          {e.username}
                        </UserHoverCard>
                        {isMe && (
                          <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-stone-200 rounded">
                            나
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right text-green-600 font-medium">
                        {e.wins}
                      </td>
                      <td className="px-4 py-2 text-right text-red-600 font-medium">
                        {e.losses}
                      </td>
                      <td className="px-4 py-2 text-right text-stone-700">
                        {winRate}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <p className="text-xs text-stone-500 text-center">
          AI 게임 결과 포함. 경기를 한 번도 끝내지 않은 사용자는 표시되지 않습니다.
        </p>
      </div>
    </div>
  );
}
