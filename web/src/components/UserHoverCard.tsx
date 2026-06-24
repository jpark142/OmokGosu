// Wraps a username. On hover (with a short delay so it doesn't flash) fetches
// the user's recent matches and shows them in a floating panel. Lazy: no
// network call until the first hover, and the result is cached per mount.

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

import { getRecentMatches } from "@/lib/api";
import type { GameOverReason, MatchSummary } from "@/types/protocol";

// w-72 in tailwind = 288px. Used both for the className and the
// right-edge clamp so the card stays inside the viewport on narrow
// screens or when triggered near the right gutter.
const CARD_WIDTH_PX = 288;
const CARD_MARGIN_PX = 8;

const OVER_REASON_LABEL: Record<GameOverReason, string> = {
  FIVE: "5목",
  OVERLINE_WIN: "장목",
  RESIGN: "기권",
  TIMEOUT: "시간패",
  DRAW: "무승부",
  ABORTED: "무효",
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

interface Props {
  userId: number | null;
  children: React.ReactNode;  // the username text (or any trigger)
}

export default function UserHoverCard({ userId, children }: Props) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const [matches, setMatches] = useState<MatchSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const fetchedRef = useRef(false);
  const enterTimer = useRef<number | null>(null);
  const leaveTimer = useRef<number | null>(null);
  const triggerRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    return () => {
      if (enterTimer.current !== null) window.clearTimeout(enterTimer.current);
      if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
    };
  }, []);

  // Position the card just below the trigger, clamped to the viewport so
  // it doesn't overflow on the right edge. Computed at hover time —
  // hover cards are short-lived enough that scroll-tracking would be
  // more code than it's worth.
  const updateCoords = () => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const maxLeft = window.innerWidth - CARD_WIDTH_PX - CARD_MARGIN_PX;
    const left = Math.max(CARD_MARGIN_PX, Math.min(rect.left, maxLeft));
    setCoords({ top: rect.bottom + 4, left });
  };

  // If userId is null (e.g., AI slot), no hover behavior at all.
  if (userId === null) {
    return <>{children}</>;
  }

  const fetchOnce = async () => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    try {
      const r = await getRecentMatches(userId);
      setMatches(r.matches);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const onEnter = () => {
    if (leaveTimer.current !== null) {
      window.clearTimeout(leaveTimer.current);
      leaveTimer.current = null;
    }
    enterTimer.current = window.setTimeout(() => {
      updateCoords();
      setOpen(true);
      void fetchOnce();
    }, 300);
  };

  const onLeave = () => {
    if (enterTimer.current !== null) {
      window.clearTimeout(enterTimer.current);
      enterTimer.current = null;
    }
    leaveTimer.current = window.setTimeout(() => setOpen(false), 150);
  };

  // Hovering onto the floating card itself must NOT close it — cancel any
  // pending leave timer so the user can scrub through match rows / click
  // the 프로필 link inside the card.
  const onCardEnter = () => {
    if (leaveTimer.current !== null) {
      window.clearTimeout(leaveTimer.current);
      leaveTimer.current = null;
    }
  };

  const now = Date.now() / 1000;

  return (
    <span
      ref={triggerRef}
      className="inline-block"
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <Link
        to={`/users/${userId}`}
        className="cursor-pointer underline decoration-dotted decoration-stone-300 underline-offset-2 hover:decoration-stone-500"
      >
        {children}
      </Link>
      {open && createPortal(
        <div
          // Portal to <body> + fixed positioning so the card escapes any
          // ancestor with overflow:hidden (e.g. the leaderboard table
          // wrapper). z-50 keeps it above modals.
          className="fixed z-50 w-72 bg-white border border-stone-200 rounded-md shadow-lg p-3 text-left"
          style={{ top: coords.top, left: coords.left }}
          onMouseEnter={onCardEnter}
          onMouseLeave={onLeave}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium text-stone-500">최근 경기</div>
            <Link
              to={`/users/${userId}`}
              className="text-xs text-amber-600 hover:text-amber-700"
            >
              프로필 →
            </Link>
          </div>
          {loading && <div className="text-xs text-stone-400">불러오는 중...</div>}
          {error && <div className="text-xs text-red-500">불러올 수 없습니다</div>}
          {!loading && !error && matches !== null && matches.length === 0 && (
            <div className="text-xs text-stone-400">아직 완료된 경기가 없습니다</div>
          )}
          {!loading && !error && matches !== null && matches.length > 0 && (
            <ul className="space-y-1.5">
              {matches.map((m) => (
                <li key={m.match_id}>
                  <Link
                    to={`/matches/${m.match_id}`}
                    className="text-xs flex items-center gap-2 hover:bg-stone-50 rounded px-1 py-0.5 -mx-1"
                    title="기보 다시 보기"
                  >
                    <span
                      className={`inline-block w-1 h-4 rounded ${
                        m.is_aborted
                          ? "bg-stone-300"
                          : m.is_draw
                            ? "bg-stone-400"
                            : m.you_won
                              ? "bg-green-500"
                              : "bg-red-400"
                      }`}
                    />
                    <span
                      className={`font-semibold ${m.is_aborted ? "w-10" : "w-7"} ${
                        m.is_aborted || m.is_draw
                          ? "text-stone-600"
                          : m.you_won
                            ? "text-green-700"
                            : "text-red-600"
                      }`}
                    >
                      {m.is_aborted ? "무효" : m.is_draw ? "무" : m.you_won ? "승" : "패"}
                    </span>
                    <span className="text-stone-700 truncate flex-1 flex items-center gap-1 min-w-0">
                      {m.is_ai_game ? (
                        <span className="inline-flex items-center text-[10px] leading-none px-1 py-0.5 bg-amber-100 text-amber-800 rounded font-medium shrink-0">
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
                    <span className="text-stone-400 whitespace-nowrap">
                      {OVER_REASON_LABEL[m.over_reason]} ·{" "}
                      {formatRelative(now - m.ended_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>,
        document.body,
      )}
    </span>
  );
}
