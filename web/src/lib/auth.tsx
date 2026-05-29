// AuthProvider: holds the current user and the login/logout/register flow.
// Token persists in localStorage; the actual REST roundtrips live in fetcher.ts.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { getToken, http, HttpError, setToken } from "@/lib/fetcher";
import type { AuthResponse, UserSummary } from "@/types/protocol";

interface AuthValue {
  user: UserSummary | null;
  token: string | null;
  initializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
  applyStats: (wins: number, losses: number) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [token, setTokenState] = useState<string | null>(getToken());
  const [initializing, setInitializing] = useState(true);

  // On boot: if we have a token, validate it by fetching /me. If 401, drop.
  useEffect(() => {
    let cancelled = false;
    const t = getToken();
    if (!t) {
      setInitializing(false);
      return;
    }
    http
      .get<UserSummary>("/api/auth/me")
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setTokenState(t);
      })
      .catch(() => {
        if (cancelled) return;
        setToken(null);
        setTokenState(null);
        setUser(null);
      })
      .finally(() => {
        if (!cancelled) setInitializing(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Global 401 handler: drop user, redirect handled by route guards.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setTokenState(null);
    };
    window.addEventListener("omok:unauthorized", onUnauthorized);
    return () => window.removeEventListener("omok:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await http.post<AuthResponse>("/api/auth/login", { username, password });
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
    } catch (e) {
      if (e instanceof HttpError && e.status === 401) {
        throw new Error("아이디 또는 비밀번호가 잘못되었습니다");
      }
      throw e;
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    try {
      const res = await http.post<AuthResponse>("/api/auth/register", { username, password });
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
      toast.success(`환영합니다, ${res.user.username}!`);
    } catch (e) {
      if (e instanceof HttpError && e.status === 409) {
        throw new Error("이미 사용 중인 닉네임입니다");
      }
      throw e;
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const refreshMe = useCallback(async () => {
    if (!getToken()) return;
    try {
      const u = await http.get<UserSummary>("/api/auth/me");
      setUser(u);
    } catch {
      /* swallow — handler above already dropped on 401 */
    }
  }, []);

  // Optimistic update from WS SGameOverMsg.stats_updates (avoids /me round-trip).
  const applyStats = useCallback((wins: number, losses: number) => {
    setUser((prev) => (prev ? { ...prev, wins, losses } : prev));
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ user, token, initializing, login, register, logout, refreshMe, applyStats }),
    [user, token, initializing, login, register, logout, refreshMe, applyStats],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(AuthContext);
  if (v === null) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
