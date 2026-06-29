import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";

type Tab = "login" | "register";

// Mirror of server/omok_server/auth/username_rules.py. Keeping the rules in
// two places isn't ideal, but server is authoritative — this is purely for
// pre-submit UX (live counter, disabled button) so a user doesn't post and
// then bounce off a 400. Server validates again on receipt.
const USERNAME_MIN_WIDTH = 4;  // 2 Korean chars or 4 Latin
const USERNAME_MAX_WIDTH = 12; // 6 Korean chars or 12 Latin
// Only complete Hangul syllables, Latin, digits — no bare jamo anywhere
// (blocks "ㅋㅋ", "이ㅇ", …). Profanity is screened server-side.
const USERNAME_ALLOWED_RE = /^[0-9A-Za-z가-힣]+$/;

function charWidth(ch: string): number {
  const code = ch.codePointAt(0) ?? 0;
  // Hangul Syllables (가-힣) and Hangul Jamo (ㄱ-ㅣ) — both East Asian Wide.
  if ((code >= 0xac00 && code <= 0xd7a3) || (code >= 0x3131 && code <= 0x318e)) {
    return 2;
  }
  return 1;
}

function usernameWidth(name: string): number {
  let w = 0;
  for (const ch of name) w += charWidth(ch);
  return w;
}

function usernameError(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) return "닉네임을 입력하세요";
  if (!USERNAME_ALLOWED_RE.test(trimmed))
    return "닉네임은 한글·영문·숫자만 사용할 수 있습니다 (단독 자음·모음 불가)";
  const w = usernameWidth(trimmed);
  if (w < USERNAME_MIN_WIDTH)
    return "닉네임은 한글 2자 (또는 영문·숫자 4자) 이상";
  if (w > USERNAME_MAX_WIDTH)
    return "닉네임은 한글 6자 (또는 영문·숫자 12자) 까지";
  return null;
}

export default function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [tab, setTab] = useState<Tab>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const usernameW = usernameWidth(username.trim());
  // On the register tab we surface field-level errors live; on login we trust
  // the user is recalling an existing account and let the server speak.
  const liveUsernameError = tab === "register" ? usernameError(username) : null;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (tab === "register") {
      const err = usernameError(username);
      if (err) {
        toast.error(err);
        return;
      }
    }
    if (password.length < 4) {
      toast.error("비밀번호는 4자 이상입니다");
      return;
    }
    setBusy(true);
    try {
      if (tab === "login") {
        await login(username, password);
      } else {
        await register(username.trim(), password);
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
          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <label className="text-sm font-medium text-stone-700">닉네임</label>
              {tab === "register" && (
                <span
                  className={`text-[11px] tabular-nums ${
                    usernameW > USERNAME_MAX_WIDTH ? "text-red-500" : "text-stone-400"
                  }`}
                >
                  {usernameW} / {USERNAME_MAX_WIDTH}
                </span>
              )}
            </div>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={12}
              className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 ${
                liveUsernameError
                  ? "border-red-300 focus:ring-red-400"
                  : "border-stone-300 focus:ring-amber-400"
              }`}
              placeholder={tab === "register" ? "한글 2-6자 또는 영문·숫자 4-12자" : "닉네임"}
            />
            {liveUsernameError && (
              <p className="text-[11px] text-red-500">{liveUsernameError}</p>
            )}
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
      </div>
    </div>
  );
}
