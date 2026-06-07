// /matches/:matchId — step through a finished game's moves.
//
// Loads the full match (GET /api/matches/:id) once, then renders the existing
// Board component with a sliced subset of stones. Controls scrub through with
// keyboard arrows + buttons.

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Board from "@/components/Board";
import { getMatch } from "@/lib/api";
import { HttpError } from "@/lib/fetcher";
import type { GameOverReason, MatchDetail } from "@/types/protocol";

const REASON_LABEL: Record<GameOverReason, string> = {
  FIVE: "5목",
  OVERLINE_WIN: "장목 승 (백)",
  RESIGN: "기권",
  TIMEOUT: "시간패",
  DRAW: "판 가득 (무승부)",
  ABORTED: "무효 (대국 시작 전 기권)",
};

export default function MatchReplay() {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);  // 0 = empty board, 1..N = after move N

  useEffect(() => {
    if (!matchId) return;
    const id = Number(matchId);
    if (Number.isNaN(id)) {
      setError("잘못된 경기 번호입니다");
      return;
    }
    let cancelled = false;
    getMatch(id)
      .then((m) => {
        if (cancelled) return;
        setMatch(m);
        setIdx(m.moves.length);  // start at the final position
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof HttpError) {
          if (e.status === 403) setError("이 경기를 볼 권한이 없습니다");
          else if (e.status === 404) setError("경기를 찾을 수 없습니다");
          else setError(`불러오기 실패: ${e.message}`);
        } else {
          setError("불러오기 실패");
        }
      });
    return () => { cancelled = true; };
  }, [matchId]);

  // Keyboard navigation.
  useEffect(() => {
    if (!match) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") setIdx((i) => Math.max(0, i - 1));
      else if (e.key === "ArrowRight") setIdx((i) => Math.min(match.moves.length, i + 1));
      else if (e.key === "Home") setIdx(0);
      else if (e.key === "End") setIdx(match.moves.length);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [match]);

  const visibleStones = useMemo(() => (match ? match.moves.slice(0, idx) : []), [match, idx]);
  const lastMove = idx > 0 && match ? match.moves[idx - 1] : null;

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

  if (!match) {
    return (
      <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm">
        불러오는 중...
      </div>
    );
  }

  const winnerLabel =
    match.over_reason === "ABORTED"
      ? "무효"
      : match.winner_color === null
        ? "무승부"
        : match.winner_color === "BLACK"
          ? `흑 (${match.black_username ?? "?"}) 승`
          : `백 (${match.white_username ?? "?"}) 승`;

  const blackLabel = `흑: ${match.black_username ?? "?"}`;
  const whiteLabel = `백: ${match.white_username ?? "?"}`;

  return (
    <div className="min-h-screen p-4 md:p-8 bg-stone-50">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 뒤로
          </button>
          <div className="text-xs text-stone-500">
            기보 · {match.move_count}수
          </div>
        </div>

        <div className="grid md:grid-cols-[1fr_280px] gap-6">
          <div className="flex justify-center">
            <Board
              stones={visibleStones}
              lastMove={lastMove}
              disabled
              hoverColor={null}
            />
          </div>

          <div className="space-y-3">
            <div className="bg-white rounded-md border border-stone-200 p-3">
              <div className="text-xs uppercase text-stone-500 mb-1">결과</div>
              <div className="font-bold text-lg">{winnerLabel}</div>
              <div className="text-xs text-stone-500 mt-1">
                {REASON_LABEL[match.over_reason]}
              </div>
            </div>

            <div className="bg-white rounded-md border border-stone-200 p-3 text-sm space-y-1">
              <div>{blackLabel}</div>
              <div>{whiteLabel}</div>
            </div>

            <div className="bg-white rounded-md border border-stone-200 p-3 space-y-3">
              <div className="text-sm text-stone-500">
                현재: {idx} / {match.moves.length} 수
              </div>
              <input
                type="range"
                min={0}
                max={match.moves.length}
                value={idx}
                onChange={(e) => setIdx(Number(e.target.value))}
                className="w-full accent-amber-500"
              />
              <div className="grid grid-cols-4 gap-2 text-sm">
                <button
                  onClick={() => setIdx(0)}
                  className="py-2 border border-stone-300 rounded hover:bg-stone-50"
                  title="처음 (Home)"
                >
                  ⏮
                </button>
                <button
                  onClick={() => setIdx((i) => Math.max(0, i - 1))}
                  className="py-2 border border-stone-300 rounded hover:bg-stone-50"
                  title="이전 수 (←)"
                >
                  ◀
                </button>
                <button
                  onClick={() => setIdx((i) => Math.min(match.moves.length, i + 1))}
                  className="py-2 border border-stone-300 rounded hover:bg-stone-50"
                  title="다음 수 (→)"
                >
                  ▶
                </button>
                <button
                  onClick={() => setIdx(match.moves.length)}
                  className="py-2 border border-stone-300 rounded hover:bg-stone-50"
                  title="끝 (End)"
                >
                  ⏭
                </button>
              </div>
              <div className="text-xs text-stone-400 text-center">
                키보드: ← → Home End
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
