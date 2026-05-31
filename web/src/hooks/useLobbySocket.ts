import { useEffect, useRef, useState } from "react";

import { getToken } from "@/lib/fetcher";
import type { RoomSummary, ServerLobbyMsg } from "@/types/protocol";

export interface LobbySocketState {
  rooms: RoomSummary[];
  connected: boolean;
}

export function useLobbySocket(): LobbySocketState {
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let backoff = 500;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const token = getToken() ?? "";
      const url = `${proto}://${location.host}/ws/lobby?token=${encodeURIComponent(token)}`;
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
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = (ev) => {
        if (cancelled) return;
        setConnected(false);
        if (ev.code === 4401 || ev.code === 4403 || ev.code === 4404) return;
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

  return { rooms, connected };
}
