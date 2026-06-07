// AuthProvider: holds the current user and the login/logout/register flow.
// Token persists in localStorage; the actual REST roundtrips live in fetcher.ts.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { getToken, http, HttpError, setToken } from "@/lib/fetcher";
import type { AuthResponse, UserSummary } from "@/types/protocol";

interface AuthValue {
  user: UserSummary | null;
  token: string | null;
  initializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  applyStats: (wins: number, losses: number, draws?: number) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [token, setTokenState] = useState<string | null>(getToken());
  const [initializing, setInitializing] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const bootRedirectDone = useRef(false);

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
    const onUnauthorized = (ev: Event) => {
      const reason = (ev as CustomEvent<{ reason?: string }>).detail?.reason;
      if (reason === "session displaced") {
        toast.error("다른 곳에서 로그인되어 자동 로그아웃되었습니다.");
      }
      setUser(null);
      setTokenState(null);
    };
    window.addEventListener("omok:unauthorized", onUnauthorized);
    return () => window.removeEventListener("omok:unauthorized", onUnauthorized);
  }, []);

  // Auto-resume: on first render after /me resolves, if the user is in a room,
  // jump them back to it. Only runs once — afterwards the user navigates freely
  // (e.g. they can go to /lobby and look around without being snapped back).
  useEffect(() => {
    if (initializing) return;
    if (bootRedirectDone.current) return;
    bootRedirectDone.current = true;
    const roomId = user?.current_room_id;
    if (!roomId) return;
    // Only redirect from typical landing pages; if the user deep-linked
    // somewhere specific (e.g. /game/:id), respect that.
    const here = location.pathname;
    if (here === "/" || here === "/lobby" || here === "/login") {
      navigate(`/rooms/${roomId}`, { replace: true });
    }
  }, [initializing, user, navigate, location.pathname]);

  // Cleanup on tab close / refresh / navigation away: leave any rooms the user
  // is in so closing the browser as the host actually deletes the room
  // (instead of stranding an orphan that nobody can reach). fetch+keepalive
  // survives unload and carries the Authorization header.
  useEffect(() => {
    const onUnload = () => {
      const tok = getToken();
      if (!tok) return;
      try {
        fetch("/api/rooms/leave-all", {
          method: "POST",
          headers: { Authorization: `Bearer ${tok}` },
          keepalive: true,
        });
      } catch {
        /* unload — nothing to do */
      }
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
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

  const logout = useCallback(async () => {
    // Server-side: leave any rooms the user is in (deletes host rooms).
    // If it fails (network, etc.), still log out locally so the user isn't
    // stranded — orphaned rooms are recoverable next session.
    try {
      await http.post("/api/auth/logout");
    } catch {
      /* ignore — log out client-side regardless */
    }
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
  const applyStats = useCallback(
    (wins: number, losses: number, draws?: number) => {
      setUser((prev) =>
        prev
          ? { ...prev, wins, losses, draws: draws ?? prev.draws ?? 0 }
          : prev,
      );
    },
    [],
  );

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
