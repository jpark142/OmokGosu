import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";

type Tab = "login" | "register";

export default function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [tab, setTab] = useState<Tab>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (username.length < 2 || password.length < 4) {
      toast.error("닉네임은 2자 이상, 비밀번호는 4자 이상입니다");
      return;
    }
    setBusy(true);
    try {
      if (tab === "login") {
        await login(username, password);
      } else {
        await register(username, password);
      }
      navigate("/");
    } catch (e) {
      toast.error((e as Error).message || "오류가 발생했습니다");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-stone-50">
      <div className="w-full max-w-md bg-white rounded-lg shadow-lg p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">OmokGosu</h1>
          <p className="text-sm text-stone-500 mt-1">한국식 렌주룰 오목</p>
        </div>

        <div className="flex border-b border-stone-200">
          {(["login", "register"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium ${
                tab === t
                  ? "text-amber-600 border-b-2 border-amber-500"
                  : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t === "login" ? "로그인" : "회원가입"}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">닉네임</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={24}
              className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
              placeholder="2-24자"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              maxLength={128}
              className="w-full px-3 py-2 border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-amber-400"
              placeholder="4자 이상"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800 disabled:bg-stone-400"
          >
            {busy ? "처리 중..." : tab === "login" ? "로그인" : "회원가입"}
          </button>
        </form>

        <div className="text-xs text-stone-500 leading-relaxed border-t pt-4">
          렌주 룰: 흑에게 3-3 / 4-4 / 장목 금수. 색은 게임 시작 시 무작위로 배정됩니다.
        </div>
      </div>
    </div>
  );
}
