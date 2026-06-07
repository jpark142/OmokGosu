// /users/:userId — public profile page with full match history.

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getRecentMatches, getUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { HttpError } from "@/lib/fetcher";
import type {
  GameOverReason,
  MatchSummary,
  UserSummary,
} from "@/types/protocol";

const REASON_LABEL: Record<GameOverReason, string> = {
  FIVE: "5목",
  OVERLINE_WIN: "장목 승 (백)",
  RESIGN: "기권",
  TIMEOUT: "시간패",
  DRAW: "무승부",
};

function formatRelative(secondsAgo: number): string {
  if (secondsAgo < 60) return "방금";
  const min = Math.floor(secondsAgo / 60);
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  const day = Math.floor(hr / 24);
  return `${day}일 전`;
}

export default function UserProfile() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { user: me } = useAuth();
  const [profile, setProfile] = useState<UserSummary | null>(null);
  const [matches, setMatches] = useState<MatchSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const targetId = Number(userId);

  useEffect(() => {
    if (Number.isNaN(targetId)) {
      setError("잘못된 사용자 번호입니다");
      return;
    }
    let cancelled = false;
    Promise.all([getUser(targetId), getRecentMatches(targetId, 50)])
      .then(([u, r]) => {
        if (cancelled) return;
        setProfile(u);
        setMatches(r.matches);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof HttpError && e.status === 404) {
          setError("사용자를 찾을 수 없습니다");
        } else {
          setError("불러오기 실패");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [targetId]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-stone-700 text-center space-y-4">
          <div>{error}</div>
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 bg-stone-900 text-white rounded text-sm"
          >
            뒤로
          </button>
        </div>
      </div>
    );
  }

  if (!profile || !matches) {
    return (
      <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm">
        불러오는 중...
      </div>
    );
  }

  // Draws are deliberately excluded from win-rate math; only decisive
  // games (wins + losses) make up the denominator.
  const draws = profile.draws ?? 0;
  const decisive = profile.wins + profile.losses;
  const total = decisive + draws;
  const winRate = decisive > 0 ? Math.round((profile.wins / decisive) * 100) : 0;
  const isMe = me?.id === profile.id;
  const now = Date.now() / 1000;

  return (
    <div className="min-h-screen p-4 md:p-6 bg-stone-50">
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 뒤로
          </button>
          <span className="w-12" />
        </div>

        {/* Stats card */}
        <div className="bg-white rounded-md border border-stone-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <h1 className="text-2xl font-bold">{profile.username}</h1>
            {isMe && (
              <span className="text-xs px-2 py-0.5 bg-stone-200 rounded">나</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-stone-500 uppercase">전적</div>
              <div className="text-xl font-medium">
                <span className="text-green-600">{profile.wins}</span>
                {" / "}
                <span className="text-stone-500">{draws}</span>
                {" / "}
                <span className="text-red-600">{profile.losses}</span>
              </div>
              <div className="text-[10px] text-stone-400 mt-0.5">승 / 무 / 패</div>
            </div>
            <div>
              <div className="text-xs text-stone-500 uppercase">승률</div>
              <div
                className="text-xl font-medium"
                title="무승부는 승률 계산에서 제외됩니다"
              >
                {decisive > 0 ? `${winRate}%` : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-stone-500 uppercase">총 경기</div>
              <div className="text-xl font-medium">{total}</div>
            </div>
          </div>
        </div>

        {/* Match history */}
        <div className="bg-white rounded-md border border-stone-200 overflow-hidden">
          <div className="px-4 py-2 text-xs uppercase text-stone-500 border-b border-stone-100">
            경기 기록 (최근 {matches.length}개)
          </div>
          {matches.length === 0 ? (
            <div className="p-8 text-center text-stone-500 text-sm">
              아직 끝낸 경기가 없습니다.
            </div>
          ) : (
            <ul>
              {matches.map((m) => (
                <li key={m.match_id} className="border-t border-stone-100 first:border-t-0">
                  <Link
                    to={`/matches/${m.match_id}`}
                    className="flex items-center gap-3 px-4 py-2 hover:bg-stone-50 text-sm"
                  >
                    <span
                      className={`inline-block w-1.5 h-5 rounded ${
                        m.is_draw
                          ? "bg-stone-400"
                          : m.you_won
                            ? "bg-green-500"
                            : "bg-red-400"
                      }`}
                    />
                    <span
                      className={`font-semibold w-8 ${
                        m.is_draw
                          ? "text-stone-600"
                          : m.you_won
                            ? "text-green-700"
                            : "text-red-600"
                      }`}
                    >
                      {m.is_draw ? "무" : m.you_won ? "승" : "패"}
                    </span>
                    <span className="flex-1 truncate flex items-center gap-2 min-w-0">
                      {m.is_ai_game ? (
                        <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded font-medium shrink-0">
                          vs AI
                        </span>
                      ) : (
                        <span className="truncate">
                          {m.opponent_username ?? "(탈퇴한 유저)"}
                        </span>
                      )}
                      <span className="text-stone-400 whitespace-nowrap">
                        · {m.your_color === "BLACK" ? "흑" : "백"}
                      </span>
                    </span>
                    <span className="text-stone-400 text-xs whitespace-nowrap">
                      {REASON_LABEL[m.over_reason]} · {formatRelative(now - m.ended_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
