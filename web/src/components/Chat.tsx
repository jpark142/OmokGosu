// Reusable chat panel. Used by Lobby, Room, and Game. Receives the message
// list + a send callback as props so each context can plug in its own WS.

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "@/lib/auth";
import type { ChatMessage } from "@/types/protocol";

interface Props {
  title?: string;
  messages: ChatMessage[];
  onSend: (text: string) => void;
  disabled?: boolean;
  className?: string;
  /**
   * Scroller height bucket.
   *   sm = ~3 messages visible (room / in-game side panel)
   *   md = default, ~6 messages
   *   lg = lobby — main attraction, ~10 messages
   */
  size?: "sm" | "md" | "lg";
}

const HEIGHT_BY_SIZE = {
  sm: "h-40",   // 160px
  md: "h-72",   // 288px
  lg: "h-96",   // 384px
} as const;

function formatTime(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export default function Chat({
  title = "채팅",
  messages,
  onSend,
  disabled = false,
  className = "",
  size = "md",
}: Props) {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new messages.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed.slice(0, 200));
    setText("");
  };

  return (
    <div
      className={`bg-white border border-stone-200 rounded-md flex flex-col ${className}`}
    >
      <div className="px-3 py-2 border-b border-stone-100 text-xs uppercase text-stone-500 flex justify-between items-center">
        <span>{title}</span>
        <span className="text-stone-400">{messages.length}</span>
      </div>
      <div
        ref={scrollerRef}
        className={`overflow-y-auto p-3 space-y-1 text-sm ${HEIGHT_BY_SIZE[size]}`}
      >
        {messages.length === 0 ? (
          <div className="text-xs text-stone-400 text-center py-4">
            아직 메시지가 없습니다. 가볍게 인사 한 번?
          </div>
        ) : (
          messages.map((m, i) => {
            // System messages render as a centered italic banner.
            if (m.is_system) {
              return (
                <div
                  key={i}
                  className="text-center text-xs text-stone-400 italic py-1"
                >
                  {m.text}
                </div>
              );
            }
            const isMe = user?.id === m.user_id;
            return (
              <div key={i} className="flex gap-2 items-baseline">
                <span className="text-[10px] text-stone-400 w-14 shrink-0 font-mono">
                  {formatTime(m.server_time_ms)}
                </span>
                <Link
                  to={`/users/${m.user_id}`}
                  className={`shrink-0 truncate max-w-[8rem] ${
                    isMe ? "font-bold text-amber-600" : "font-medium text-stone-700"
                  } hover:underline`}
                  title="프로필 보기"
                >
                  {m.username}
                </Link>
                <span className="text-stone-700 break-words min-w-0">{m.text}</span>
              </div>
            );
          })
        )}
      </div>
      <div className="border-t border-stone-100 p-2 flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            // `isComposing` is true while Korean (or other IME) is mid-composition.
            // Pressing Enter then should commit the composition, not submit the
            // form, otherwise typed-but-uncomposed characters get sent.
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={disabled}
          maxLength={200}
          placeholder={disabled ? "연결 중..." : "메시지... (Enter)"}
          className="flex-1 px-2 py-1 border border-stone-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:bg-stone-50"
        />
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="px-3 py-1 bg-stone-900 text-white rounded text-sm hover:bg-stone-800 disabled:bg-stone-300"
        >
          전송
        </button>
      </div>
    </div>
  );
}
