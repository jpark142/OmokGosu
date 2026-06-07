// Thin fetch wrapper that injects the JWT and unwraps JSON / errors uniformly.
//
// Token storage: sessionStorage (per-tab) so multiple browser windows can log
// in as different users — critical for local multi-user testing. Trade-off:
// closing the tab clears the login. localStorage (shared across all tabs of
// one origin) was tried first but caused the "second login silently kicked
// the first" bug.

import { CLIENT_VERSION } from "@/lib/version";

const TOKEN_KEY = "omok_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token === null) sessionStorage.removeItem(TOKEN_KEY);
  else sessionStorage.setItem(TOKEN_KEY, token);
}

export class HttpError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type Json = Record<string, unknown> | Array<unknown> | null;

async function request<T>(
  method: string,
  path: string,
  body?: Json,
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Client-Version": CLIENT_VERSION,
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const tok = getToken();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;

  const res = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    setToken(null);
    // Peek the body for the server's reason (e.g. "session displaced" when
    // another login retired this token) so AuthProvider can pick a more
    // specific toast than the generic "session expired" message.
    let reason: string | undefined;
    try {
      const peek = res.clone();
      const body = await peek.json();
      if (body && typeof body === "object" && "detail" in body) {
        reason = String((body as { detail: unknown }).detail);
      }
    } catch {
      /* no body or not JSON — fall through with reason=undefined */
    }
    window.dispatchEvent(new CustomEvent("omok:unauthorized", { detail: { reason } }));
  }

  if (res.status === 426) {
    // Server rejected our version. VersionProvider listens for this and
    // promotes to "hard" immediately — no need to wait for the next poll tick.
    window.dispatchEvent(new CustomEvent("omok:upgrade-required"));
  }

  let payload: unknown = null;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    try { payload = await res.json(); } catch { /* fallthrough */ }
  }
  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `${method} ${path} ${res.status}`;
    throw new HttpError(res.status, payload, detail);
  }
  return payload as T;
}

export const http = {
  get:  <T,>(path: string)              => request<T>("GET",    path),
  post: <T,>(path: string, body?: Json) => request<T>("POST",   path, body ?? {}),
  del:  <T,>(path: string)              => request<T>("DELETE", path),
};

/** Called from every WS hook's onclose when code === 4401. Mirrors the REST
 * 401 path: drops the token and dispatches the unauthorized event so
 * AuthProvider can show the displaced toast and route-guards take over.
 * Suppressed within ~3s of a fresh login so the server-side close that retires
 * the *previous* token doesn't kick the new session out. */
export function handleWsUnauthorized(): void {
  const sentinel = (window as unknown as { __omokJustLoggedInAt?: number }).__omokJustLoggedInAt;
  if (sentinel && Date.now() - sentinel < 3000) return;
  setToken(null);
  window.dispatchEvent(
    new CustomEvent("omok:unauthorized", { detail: { reason: "session displaced" } }),
  );
}
