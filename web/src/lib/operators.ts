// Operator (운영자) registry on the client. Fetched once from /api/operators
// and cached module-wide; components subscribe via `useIsOperator` so they
// re-render when the list arrives. Matching is case-insensitive, mirroring the
// server.

import { useEffect, useReducer } from "react";

import { http } from "@/lib/fetcher";

interface OperatorsInfo {
  usernames: string[];
}

let operatorKeys = new Set<string>();
let loaded = false;
let loading = false;
const subscribers = new Set<() => void>();

function notify() {
  subscribers.forEach((cb) => cb());
}

async function load() {
  if (loaded || loading) return;
  loading = true;
  try {
    const info = await http.get<OperatorsInfo>("/api/operators");
    operatorKeys = new Set((info.usernames ?? []).map((u) => u.toLowerCase()));
  } catch {
    // Leave the set empty — no badges is a safe degradation.
  } finally {
    loaded = true;
    loading = false;
    notify();
  }
}

/** Case-insensitive operator check. Returns false until the list has loaded. */
export function isOperatorName(username?: string | null): boolean {
  return !!username && operatorKeys.has(username.trim().toLowerCase());
}

/**
 * Returns a stable `isOperator(name)` checker and triggers the one-time fetch.
 * The component re-renders once the list loads so badges appear without a
 * manual refresh.
 */
export function useIsOperator(): (username?: string | null) => boolean {
  const [, force] = useReducer((x: number) => x + 1, 0);
  useEffect(() => {
    if (loaded) return;
    const cb = () => force();
    subscribers.add(cb);
    void load();
    return () => {
      subscribers.delete(cb);
    };
  }, []);
  return isOperatorName;
}
