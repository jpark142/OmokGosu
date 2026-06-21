import { useEffect, useRef, useState } from "react";

import { getToken, handleWsUnauthorized } from "@/lib/fetcher";
import { CLIENT_VERSION } from "@/lib/version";
import type { ChatMessage, RoomSummary, ServerLobbyMsg } from "@/types/protocol";

export interface LobbySocketState {
  rooms: RoomSummary[];
  connected: boolean;
  chat: ChatMessage[];
  sendChat: (text: string) => void;
}

export function useLobbySocket(): LobbySocketState {
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [connected, setConnected] = useState(false);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let backoff = 500;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const params = new URLSearchParams();
      const token = getToken();
      if (token) params.set("token", token);
      params.set("client_version", CLIENT_VERSION);
      const url = `${proto}://${location.host}/ws/lobby?${params}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) {
          setConnected(true);
          backoff = 500;
        }
      };
      ws.onmessage = (ev) => {
        if (cancelled) return;
        try {
          const msg = JSON.parse(ev.data) as ServerLobbyMsg;
          if (msg.type === "lobby_snapshot") {
            setRooms(msg.rooms);
          } else if (msg.type === "lobby_update") {
            setRooms((prev) => {
              const without = prev.filter((r) => r.room_id !== msg.room_id);
              if (msg.action === "removed" || msg.room === null) return without;
              return [...without, msg.room].sort((a, b) => b.created_at - a.created_at);
            });
          } else if (msg.type === "chat_history") {
            setChat(msg.messages);
          } else if (msg.type === "chat") {
            const { user_id, username, text, server_time_ms, is_system, role, is_blurred } = msg;
            setChat((prev) => [
              ...prev,
              { user_id, username, text, server_time_ms, is_system, role, is_blurred },
            ]);
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = (ev) => {
        if (cancelled) return;
        setConnected(false);
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
  }, []);

  const sendChat = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "chat", text: trimmed.slice(0, 200) }));
    }
  };

  return { rooms, connected, chat, sendChat };
}
