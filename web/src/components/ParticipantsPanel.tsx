// Side panel for the in-game UI: shows who is in the room (the 2 players
// listed first, then the live spectators). Each row links to the user's
// profile via UserHoverCard so the reader can peek at recent matches.

import UserHoverCard from "@/components/UserHoverCard";
import type { ColorStr, PlayerInfo, SpectatorInfo } from "@/types/protocol";

interface Props {
  blackPlayer: PlayerInfo | undefined;
  whitePlayer: PlayerInfo | undefined;
  spectators: SpectatorInfo[];
}

function formatStats(
  wins: number | null | undefined,
  losses: number | null | undefined,
  draws: number | null | undefined,
): string | null {
  if (wins === undefined || wins === null) return null;
  if (losses === undefined || losses === null) return null;
  const d = draws ?? 0;
  return d > 0 ? `${wins}승 ${d}무 ${losses}패` : `${wins}승 ${losses}패`;
}

function RankBadge({ rank }: { rank: number | null | undefined }) {
  if (rank === null || rank === undefined) return null;
  // Top 3 get medals (same mapping as Leaderboard.tsx); 4+ falls back to "#N".
  if (rank === 1) return <span className="text-sm shrink-0" title="1위">🥇</span>;
  if (rank === 2) return <span className="text-sm shrink-0" title="2위">🥈</span>;
  if (rank === 3) return <span className="text-sm shrink-0" title="3위">🥉</span>;
  return (
    <span className="text-[10px] font-semibold text-stone-500 bg-stone-100 rounded px-1 py-0.5 shrink-0">
      #{rank}
    </span>
  );
}

function PlayerRow({ color, info }: { color: ColorStr; info: PlayerInfo | undefined }) {
  const dotClass =
    color === "BLACK"
      ? "bg-stone-900 border-stone-900"
      : "bg-white border-stone-400";
  const stats = info ? formatStats(info.wins, info.losses, info.draws) : null;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`inline-block w-3 h-3 rounded-full border ${dotClass}`}
        aria-hidden
      />
      <span className="text-[10px] uppercase text-stone-400 w-5 shrink-0">
        {color === "BLACK" ? "흑" : "백"}
      </span>
      {info ? (
        info.kind === "ai" ? (
          <span className="font-medium text-stone-700">{info.name}</span>
        ) : (
          <UserHoverCard userId={info.user_id ?? null}>{info.name}</UserHoverCard>
        )
      ) : (
        <span className="text-stone-400">—</span>
      )}
      {info?.kind === "human" && <RankBadge rank={info.rank} />}
      {stats && <span className="text-xs text-stone-500 ml-auto">{stats}</span>}
    </div>
  );
}

function SpectatorRow({ s }: { s: SpectatorInfo }) {
  const stats = formatStats(s.wins, s.losses, s.draws);
  return (
    <div className="flex items-center gap-2 text-sm">
      <UserHoverCard userId={s.user_id}>{s.username}</UserHoverCard>
      <RankBadge rank={s.rank} />
      {stats && <span className="text-xs text-stone-500 ml-auto">{stats}</span>}
    </div>
  );
}

export default function ParticipantsPanel({
  blackPlayer,
  whitePlayer,
  spectators,
}: Props) {
  return (
    <div className="bg-white rounded-md border border-stone-200">
      <div className="px-3 py-2 border-b border-stone-100 text-xs uppercase text-stone-500 flex justify-between items-center">
        <span>참여자</span>
        <span className="text-stone-400">{2 + spectators.length}</span>
      </div>
      <div className="p-3 space-y-2">
        <PlayerRow color="BLACK" info={blackPlayer} />
        <PlayerRow color="WHITE" info={whitePlayer} />
        {spectators.length > 0 && (
          <>
            <div className="border-t border-stone-100 pt-2 text-[10px] uppercase text-stone-400">
              관전자 {spectators.length}명
            </div>
            {spectators.map((s) => (
              <SpectatorRow key={s.user_id} s={s} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
