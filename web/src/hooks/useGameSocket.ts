import { useEffect, useRef, useState } from "react";

import { getToken, handleWsUnauthorized } from "@/lib/fetcher";
import { CLIENT_VERSION } from "@/lib/version";
import type { ChatMessage, ClientMsg, ServerMsg, SStateMsg } from "@/types/protocol";

export interface GameSocketState {
  state: SStateMsg | null;
  connected: boolean;
  chat: ChatMessage[];
  sendChat: (text: string) => void;
  send: (msg: ClientMsg) => void;
  onMessage: (listener: (msg: ServerMsg) => void) => () => void;
}

export function useGameSocket(gameId: string | undefined): GameSocketState {
  const [state, setState] = useState<SStateMsg | null>(null);
  const [connected, setConnected] = useState(false);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Set<(msg: ServerMsg) => void>>(new Set());

  useEffect(() => {
    if (!gameId) return;
    let cancelled = false;
    let backoff = 500;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const token = getToken() ?? "";
      const params = new URLSearchParams();
      if (token) params.set("token", token);
      params.set("client_version", CLIENT_VERSION);
      const url = `${proto}://${location.host}/ws/games/${gameId}?${params}`;
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
          else if (msg.type === "timer_tick") {
            // Merge the live clocks / to_move / server_time_ms into the
            // existing state snapshot. Without this, state.clocks only
            // updated on full SStateMsg payloads (i.e. once per move),
            // so byo-yomi entry, the DEV clock-clip cheat, and the
            // countdown TTS effect (which depends on state) all sat
            // frozen until the next move landed.
            setState((prev) =>
              prev
                ? {
                    ...prev,
                    clocks: msg.clocks,
                    to_move: msg.to_move,
                    server_time_ms: msg.server_time_ms,
                  }
                : prev,
            );
          } else if (msg.type === "chat_history") setChat(msg.messages);
          else if (msg.type === "chat") {
            const { user_id, username, text, server_time_ms, is_system, role } = msg;
            setChat((prev) => [
              ...prev,
              { user_id, username, text, server_time_ms, is_system, role },
            ]);
          }
          for (const l of listenersRef.current) l(msg);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = (ev) => {
        if (cancelled) return;
        setConnected(false);
        // 4401=auth fail, 4403=forbidden, 4404=not found, 4426=version too old.
        // None of these are recoverable by retry; let the corresponding
        // provider (Auth/Version) handle the user-facing fallout.
        if (ev.code === 4426) {
          window.dispatchEvent(new CustomEvent("omok:upgrade-required"));
          return;
        }
        if (ev.code === 4401) {
          handleWsUnauthorized();
          return;
        }
        if (ev.code === 4403 || ev.code === 4404) return;
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

  const sendChat = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    send({ type: "chat", text: trimmed.slice(0, 200) });
  };

  return { state, connected, chat, sendChat, send, onMessage };
}
