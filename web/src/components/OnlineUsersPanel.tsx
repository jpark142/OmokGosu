// Right-rail lobby panel: live list of users currently connected to any
// channel (lobby / room / game). Pushed by the server via the `presence`
// WS message — appears/disappears automatically when sockets open/close.

import { Link } from "react-router-dom";

import { useAuth } from "@/lib/auth";
import type { OnlinePresenceUser } from "@/types/protocol";

interface Props {
  users: OnlinePresenceUser[];
}

function winRate(u: OnlinePresenceUser): string {
  const decisive = u.wins + u.losses;
  if (decisive === 0) return "—";
  return `${Math.round((u.wins / decisive) * 100)}%`;
}

export default function OnlineUsersPanel({ users }: Props) {
  const { user: me } = useAuth();

  return (
    <div className="bg-white border border-stone-200 rounded-md flex flex-col">
      <div className="px-3 py-2 border-b border-stone-100 text-xs uppercase text-stone-500 flex justify-between items-center">
        <span>접속 중</span>
        <span className="text-stone-400">{users.length}</span>
      </div>
      <div className="p-2 space-y-1 max-h-[28rem] overflow-y-auto">
        {users.length === 0 ? (
          <div className="text-xs text-stone-400 text-center py-4">
            아무도 없네요.
          </div>
        ) : (
          users.map((u) => {
            const isMe = me?.id === u.user_id;
            return (
              <div
                key={u.user_id}
                className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-stone-50"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                  <span
                    className={`truncate text-sm ${
                      isMe ? "font-bold text-amber-600" : "font-medium text-stone-800"
                    }`}
                    title={u.username}
                  >
                    {u.username}
                  </span>
                  <span className="text-[11px] text-stone-400 tabular-nums shrink-0">
                    {u.wins}승
                    {u.draws > 0 && ` · ${u.draws}무`}
                    {" · "}
                    {u.losses}패
                    {" · "}
                    {winRate(u)}
                  </span>
                </div>
                <Link
                  to={`/users/${u.user_id}`}
                  className="text-[11px] px-2 py-0.5 border border-stone-300 rounded text-stone-600 hover:bg-stone-100 hover:text-stone-900 shrink-0"
                  title={`${u.username}님의 전적 보기`}
                >
                  전적 보기
                </Link>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
