import { useEffect, useRef, useState } from "react";

import type { ClientMsg, ServerMsg, SStateMsg } from "@/types/protocol";

export interface GameSocketState {
  state: SStateMsg | null;
  connected: boolean;
  send: (msg: ClientMsg) => void;
  onMessage: (listener: (msg: ServerMsg) => void) => () => void;
}

export function useGameSocket(gameId: string | undefined): GameSocketState {
  const [state, setState] = useState<SStateMsg | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Set<(msg: ServerMsg) => void>>(new Set());

  useEffect(() => {
    if (!gameId) return;
    let cancelled = false;
    let backoff = 500;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const url = `${proto}://${location.host}/ws/games/${gameId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        setConnected(true);
        backoff = 500;
      };
      ws.onmessage = (ev) => {
        if (cancelled) return;
        try {
          const msg = JSON.parse(ev.data) as ServerMsg;
          if (msg.type === "state") setState(msg);
          for (const l of listenersRef.current) l(msg);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 8000);
      };
      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [gameId]);

  const send = (msg: ClientMsg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  };

  const onMessage = (listener: (msg: ServerMsg) => void) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  };

  return { state, connected, send, onMessage };
}
