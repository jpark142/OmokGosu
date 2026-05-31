import { useState } from "react";

import type { AIDifficulty, AILevel } from "@/types/protocol";

interface Props {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onStart: (level: AILevel, difficulty: AIDifficulty | undefined) => void;
}

export default function AIPlayDialog({ open, busy, onClose, onStart }: Props) {
  const [level, setLevel] = useState<AILevel>("minimax");
  const [difficulty, setDifficulty] = useState<AIDifficulty>("medium");

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-30">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full space-y-4">
        <h2 className="text-xl font-bold">AI와 두기</h2>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">AI 종류</label>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value as AILevel)}
            className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
          >
            <option value="minimax">Minimax (Phase 2 — α-β + TT + ID)</option>
            <option value="smart">Smart (Phase 1.5 — 패턴 휴리스틱)</option>
            <option value="random">Random (테스트용)</option>
          </select>
        </div>

        {level === "minimax" && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">난이도</label>
            <div className="flex gap-2">
              {(["easy", "medium", "hard"] as AIDifficulty[]).map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`flex-1 py-2 rounded border text-sm ${
                    difficulty === d
                      ? "bg-stone-900 text-white border-stone-900"
                      : "bg-white text-stone-700 border-stone-300"
                  }`}
                >
                  {d === "easy" ? "쉬움" : d === "medium" ? "보통" : "어려움"}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            disabled={busy}
            className="flex-1 py-2 border border-stone-300 rounded text-stone-700 hover:bg-stone-50"
          >
            취소
          </button>
          <button
            onClick={() => onStart(level, level === "minimax" ? difficulty : undefined)}
            disabled={busy}
            className="flex-1 py-2 bg-stone-900 text-white rounded hover:bg-stone-800 disabled:bg-stone-400"
          >
            {busy ? "생성 중..." : "시작"}
          </button>
        </div>
      </div>
    </div>
  );
}
