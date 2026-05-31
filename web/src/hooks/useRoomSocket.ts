import { useEffect, useRef, useState } from "react";

import { getToken } from "@/lib/fetcher";
import type {
  ClientRoomMsg,
  RoomDetail,
  ServerRoomMsg,
} from "@/types/protocol";

export interface RoomSocketState {
  room: RoomDetail | null;
  connected: boolean;
  gameId: string | null;
  closed: { reason: string } | null;
  send: (msg: ClientRoomMsg) => void;
  onMessage: (cb: (msg: ServerRoomMsg) => void) => () => void;
}

export function useRoomSocket(roomId: string | undefined): RoomSocketState {
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [connected, setConnected] = useState(false);
  const [gameId, setGameId] = useState<string | null>(null);
  const [closed, setClosed] = useState<{ reason: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Set<(msg: ServerRoomMsg) => void>>(new Set());

  useEffect(() => {
    if (!roomId) return;
    let cancelled = false;
    let backoff = 500;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const token = getToken() ?? "";
      const url = `${proto}://${location.host}/ws/rooms/${roomId}?token=${encodeURIComponent(token)}`;
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
          const msg = JSON.parse(ev.data) as ServerRoomMsg;
          if (msg.type === "room_state") setRoom(msg.room);
          else if (msg.type === "room_game_started") setGameId(msg.game_id);
          else if (msg.type === "room_closed") setClosed({ reason: msg.reason });
          for (const l of listenersRef.current) l(msg);
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
  }, [roomId]);

  const send = (msg: ClientRoomMsg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  };

  const onMessage = (cb: (msg: ServerRoomMsg) => void) => {
    listenersRef.current.add(cb);
    return () => {
      listenersRef.current.delete(cb);
    };
  };

  return { room, connected, gameId, closed, send, onMessage };
}
