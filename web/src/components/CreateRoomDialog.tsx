import { useState } from "react";

interface Props {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onCreate: (title: string, password: string) => void;
}

export default function CreateRoomDialog({ open, busy, onClose, onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [password, setPassword] = useState("");

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-30">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full space-y-4">
        <h2 className="text-xl font-bold">새 방 만들기</h2>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">방 제목</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={40}
            placeholder="예: 한판 두실 분?"
            className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">
            비밀번호 <span className="text-stone-400">(선택)</span>
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            maxLength={64}
            placeholder="비워두면 공개방"
            className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
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
            onClick={() => onCreate(title.trim(), password)}
            disabled={busy || title.trim().length === 0}
            className="flex-1 py-2 bg-stone-900 text-white rounded hover:bg-stone-800 disabled:bg-stone-400"
          >
            {busy ? "생성 중..." : "만들기"}
          </button>
        </div>
      </div>
    </div>
  );
}
