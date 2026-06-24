// Polls /api/version every 60s + on focus/visibility, and listens for the
// `omok:upgrade-required` event (fired by fetcher.ts on 426 / WS hooks on 4426).
// Returns the current classification so a Provider can render banner/modal.

import { useCallback, useEffect, useRef, useState } from "react";

import { classify, CLIENT_VERSION, type VersionStatus } from "@/lib/version";

const POLL_INTERVAL_MS = 60_000;

interface VersionInfo {
  version: string;
  min_client_version: string;
  dev_mode?: boolean;
}

export interface UseVersionCheck {
  status: VersionStatus;
  serverVersion: string | null;
  clientVersion: string;
  // True when the server reports OMOK_DEV_MODE=1 — used to conditionally
  // render owner-only debug affordances (e.g. the in-game clip-clock cheat).
  devMode: boolean;
}

export function useVersionCheck(): UseVersionCheck {
  const [status, setStatus] = useState<VersionStatus>("ok");
  const [serverVersion, setServerVersion] = useState<string | null>(null);
  const [devMode, setDevMode] = useState<boolean>(false);
  const mountedRef = useRef(true);

  const tick = useCallback(async () => {
    try {
      // Skip Authorization (not needed) but still send our version so logs
      // capture who's polling. /api/version itself is exempt from the gate.
      const res = await fetch("/api/version", {
        headers: { "X-Client-Version": CLIENT_VERSION },
      });
      if (res.status === 426) {
        if (mountedRef.current) setStatus("hard");
        return;
      }
      if (!res.ok) return;
      const info = (await res.json()) as VersionInfo;
      if (!mountedRef.current) return;
      setServerVersion(info.version);
      setDevMode(!!info.dev_mode);
      setStatus(classify(info.version, info.min_client_version, CLIENT_VERSION));
    } catch {
      /* network blip — leave previous status. Next tick will retry. */
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void tick();
    const id = window.setInterval(() => void tick(), POLL_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void tick();
    };
    const onFocus = () => void tick();
    const onForceHard = () => {
      if (mountedRef.current) setStatus("hard");
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);
    window.addEventListener("omok:upgrade-required", onForceHard);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("omok:upgrade-required", onForceHard);
    };
  }, [tick]);

  return { status, serverVersion, clientVersion: CLIENT_VERSION, devMode };
}
