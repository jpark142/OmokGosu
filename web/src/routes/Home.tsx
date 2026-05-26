import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { createGame } from "@/lib/api";
import type { AIDifficulty, AILevel, GameMode } from "@/types/protocol";

export default function Home() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<GameMode>("hvh");
  const [aiLevel, setAiLevel] = useState<AILevel>("minimax");
  const [aiDifficulty, setAiDifficulty] = useState<AIDifficulty>("medium");
  const [playerName, setPlayerName] = useState("Player");
  const [busy, setBusy] = useState(false);

  const onStart = async () => {
    setBusy(true);
    try {
      const res = await createGame({
        mode,
        ai_level: mode === "hva" ? aiLevel : undefined,
        ai_difficulty:
          mode === "hva" && aiLevel === "minimax" ? aiDifficulty : undefined,
        player_name: playerName,
      });
      navigate(`/game/${res.game_id}`);
    } catch (e) {
      toast.error("게임 생성 실패");
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white rounded-lg shadow-lg p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">OmokGosu</h1>
          <p className="text-sm text-stone-500 mt-1">
            한국식 렌주룰 오목 · 5분 + 10초 byo-yomi × 3
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">플레이어 이름</label>
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">모드</label>
          <div className="flex gap-2">
            <button
              onClick={() => setMode("hvh")}
              className={`flex-1 py-2 rounded border ${
                mode === "hvh"
                  ? "bg-amber-500 text-white border-amber-500"
                  : "bg-white text-stone-700 border-stone-300"
              }`}
            >
              사람 vs 사람
            </button>
            <button
              onClick={() => setMode("hva")}
              className={`flex-1 py-2 rounded border ${
                mode === "hva"
                  ? "bg-amber-500 text-white border-amber-500"
                  : "bg-white text-stone-700 border-stone-300"
              }`}
            >
              사람 vs AI
            </button>
          </div>
        </div>

        {mode === "hva" && (
          <>
            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-700">AI 종류</label>
              <select
                value={aiLevel}
                onChange={(e) => setAiLevel(e.target.value as AILevel)}
                className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
              >
                <option value="minimax">Minimax (Phase 2 — α-β + TT + ID)</option>
                <option value="smart">Smart (Phase 1.5 — 패턴 휴리스틱)</option>
                <option value="random">Random (테스트용)</option>
                <option value="heuristic" disabled>Heuristic+VCF (Phase 3 예정)</option>
                <option value="alphazero" disabled>AlphaZero (Phase 4 예정)</option>
              </select>
            </div>

            {aiLevel === "minimax" && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-stone-700">난이도</label>
                <div className="flex gap-2">
                  {(["easy", "medium", "hard"] as AIDifficulty[]).map((d) => (
                    <button
                      key={d}
                      onClick={() => setAiDifficulty(d)}
                      className={`flex-1 py-2 rounded border text-sm ${
                        aiDifficulty === d
                          ? "bg-stone-900 text-white border-stone-900"
                          : "bg-white text-stone-700 border-stone-300"
                      }`}
                    >
                      {d === "easy" ? "쉬움 (depth 4)" : d === "medium" ? "보통 (depth 6)" : "어려움 (depth 8)"}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        <button
          onClick={onStart}
          disabled={busy}
          className="w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800 disabled:bg-stone-400"
        >
          {busy ? "생성 중..." : "게임 시작"}
        </button>

        <div className="text-xs text-stone-500 leading-relaxed border-t pt-4">
          렌주는 흑에게 3-3 / 4-4 / 장목 금수가 적용됩니다. 색은 무작위로 배정됩니다.
        </div>
      </div>
    </div>
  );
}
