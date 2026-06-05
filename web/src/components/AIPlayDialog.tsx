// Difficulty-only AI selector. The 3 levels each map to a different underlying
// engine: a 1-ply heuristic, a deep alpha-beta search, and the search + VCF
// composite. The user just picks how hard they want the opponent to be —
// the engine choice is an implementation detail.

import { useState } from "react";

import type { AIDifficulty, AILevel } from "@/types/protocol";

interface Props {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onStart: (level: AILevel, difficulty: AIDifficulty | undefined) => void;
}

interface Tier {
  difficulty: AIDifficulty;
  label: string;
  desc: string;
  level: AILevel;
  // Difficulty arg to the chosen level (server only uses this for search-based AIs).
  searchDifficulty: AIDifficulty | undefined;
}

const TIERS: Tier[] = [
  {
    difficulty: "easy",
    label: "쉬움",
    desc: "오목을 처음 두는 분께 추천",
    level: "smart",
    searchDifficulty: undefined,
  },
  {
    difficulty: "medium",
    label: "보통",
    desc: "한 번 실수하면 따라잡기 어려워요",
    level: "minimax",
    searchDifficulty: "medium",
  },
  {
    difficulty: "hard",
    label: "어려움",
    desc: "빈틈을 거의 주지 않아요",
    level: "heuristic",
    searchDifficulty: "hard",
  },
];

export default function AIPlayDialog({ open, busy, onClose, onStart }: Props) {
  const [picked, setPicked] = useState<AIDifficulty>("medium");

  if (!open) return null;

  const tier = TIERS.find((t) => t.difficulty === picked)!;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-30">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full space-y-4">
        <h2 className="text-xl font-bold">AI와 두기</h2>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">난이도</label>
          <div className="grid grid-cols-3 gap-2">
            {TIERS.map((t) => (
              <button
                key={t.difficulty}
                onClick={() => setPicked(t.difficulty)}
                className={`py-3 rounded border text-sm font-medium ${
                  picked === t.difficulty
                    ? "bg-stone-900 text-white border-stone-900"
                    : "bg-white text-stone-700 border-stone-300 hover:border-stone-400"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-stone-500 mt-1">{tier.desc}</p>
        </div>

        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            disabled={busy}
            className="flex-1 py-2 border border-stone-300 rounded text-stone-700 hover:bg-stone-50"
          >
            취소
          </button>
          <button
            onClick={() => onStart(tier.level, tier.searchDifficulty)}
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
