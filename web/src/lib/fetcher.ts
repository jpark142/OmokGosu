// Thin fetch wrapper that injects the JWT and unwraps JSON / errors uniformly.
//
// Token storage: sessionStorage (per-tab) so multiple browser windows can log
// in as different users — critical for local multi-user testing. Trade-off:
// closing the tab clears the login. localStorage (shared across all tabs of
// one origin) was tried first but caused the "second login silently kicked
// the first" bug.

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
  const headers: Record<string, string> = {};
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
    // Let the caller decide whether to redirect; AuthProvider listens on storage too.
    window.dispatchEvent(new CustomEvent("omok:unauthorized"));
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
