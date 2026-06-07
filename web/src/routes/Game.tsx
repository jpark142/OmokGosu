import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import Board from "@/components/Board";
import Chat from "@/components/Chat";
import Clock from "@/components/Clock";
import { useGameSocket } from "@/hooks/useGameSocket";
import { useAuth } from "@/lib/auth";
import type {
  ColorStr,
  ForbiddenReason,
  GameOverReason,
  PlayerInfo,
} from "@/types/protocol";

const FORBIDDEN_LABEL: Record<ForbiddenReason, string> = {
  DOUBLE_THREE: "금수: 삼삼 (3-3)",
  DOUBLE_FOUR: "금수: 사사 (4-4)",
  OVERLINE: "금수: 장목 (6목 이상)",
  NOT_YOUR_TURN: "내 차례가 아닙니다",
  OCCUPIED: "이미 돌이 있는 자리입니다",
  OUT_OF_BOUNDS: "보드 밖입니다",
  GAME_OVER: "게임이 이미 종료되었습니다",
};

const REASON_LABEL: Record<GameOverReason, string> = {
  FIVE: "5목",
  OVERLINE_WIN: "장목 승 (백)",
  RESIGN: "기권",
  TIMEOUT: "시간패",
};

function PlayerLine({ info }: { info: PlayerInfo | undefined }) {
  if (!info) return <span className="text-stone-400">—</span>;
  const stats =
    info.wins !== undefined && info.wins !== null && info.losses !== undefined && info.losses !== null
      ? `${info.wins}승 ${info.losses}패`
      : null;
  return (
    <div>
      <div className="text-xs uppercase text-stone-500">
        {info.kind === "ai" ? "AI" : "Player"}
      </div>
      <div className="font-medium">{info.name}</div>
      {stats && <div className="text-xs text-stone-500">{stats}</div>}
    </div>
  );
}

export default function Game() {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const { user, applyStats } = useAuth();
  const { state, connected, chat, sendChat, send, onMessage } = useGameSocket(gameId);
  const [gameOver, setGameOver] = useState<{
    winner: ColorStr | null;
    reason: GameOverReason;
    backToRoom: string | null;
    matchId: number | null;
  } | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  // Confirm-leave modal: set the pending destination URL when the user clicks
  // "← 홈" mid-game. Null means no confirmation in flight.
  const [pendingExit, setPendingExit] = useState<string | null>(null);

  useEffect(() => {
    const unsub = onMessage((msg) => {
      if (msg.type === "forbidden_move_rejected") {
        toast.error(FORBIDDEN_LABEL[msg.reason]);
      } else if (msg.type === "game_over") {
        setGameOver({
          winner: msg.winner,
          reason: msg.reason,
          backToRoom: msg.back_to_room ?? null,
          matchId: msg.match_id ?? null,
        });
        if (user && msg.stats_updates) {
          const mine = msg.stats_updates.find((s) => s.user_id === user.id);
          if (mine) applyStats(mine.wins, mine.losses);
        }
      } else if (msg.type === "error") {
        toast.error(msg.message);
      }
    });
    return unsub;
  }, [onMessage, user, applyStats]);

  // If the game was hosted by a room, auto-return after 5s.
  useEffect(() => {
    if (!gameOver?.backToRoom) return;
    setCountdown(5);
    const target = gameOver.backToRoom;
    const tickId = window.setInterval(() => {
      setCountdown((c) => {
        if (c === null) return null;
        if (c <= 1) {
          window.clearInterval(tickId);
          navigate(`/rooms/${target}`);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => window.clearInterval(tickId);
  }, [gameOver, navigate]);

  const blackPlayer = state?.players.BLACK;
  const whitePlayer = state?.players.WHITE;

  // Which color is "me"? In HVH, the user matches whichever player slot has
  // their user_id. In HVA, the user is the human player (the only non-AI slot).
  // In legacy/solo HVH where both slots share user_id, we let them play both.
  const myColor: ColorStr | "BOTH" | null = useMemo(() => {
    if (!user || !state) return null;
    const blackIsMe = blackPlayer?.user_id === user.id;
    const whiteIsMe = whitePlayer?.user_id === user.id;
    if (blackIsMe && whiteIsMe) return "BOTH";
    if (blackIsMe) return "BLACK";
    if (whiteIsMe) return "WHITE";
    return null;
  }, [user, state, blackPlayer, whitePlayer]);

  const lastMove = state?.last_move ?? null;
  const forbidden = state?.forbidden_squares ?? [];
  const toMove = state?.to_move ?? "BLACK";
  const myTurn =
    myColor !== null && (myColor === "BOTH" || myColor === toMove);
  const disabled = !state || state.status === "OVER" || !connected || !myTurn;

  const onPlay = (r: number, c: number) => {
    if (!state || state.status === "OVER") return;
    if (!myTurn) {
      toast.error("상대 차례입니다");
      return;
    }
    send({ type: "move", r, c });
  };

  const onResign = () => {
    if (!state || !myColor || myColor === "BOTH") {
      if (state) send({ type: "resign", color: state.to_move });
      return;
    }
    send({ type: "resign", color: myColor });
  };

  // "← 홈" handler. If the game is still IN_PROGRESS, open a confirm dialog
  // — leaving mid-game counts as a resignation. After game-over the same
  // button just navigates (no resignation needed).
  const onHomeClick = () => {
    if (!state || state.status === "OVER") {
      navigate("/");
      return;
    }
    setPendingExit("/");
  };

  const confirmLeaveAndResign = () => {
    onResign();
    const dest = pendingExit ?? "/";
    setPendingExit(null);
    navigate(dest);
  };

  const winnerText = useMemo(() => {
    if (!gameOver) return null;
    if (gameOver.winner === null) return "무승부";
    return gameOver.winner === "BLACK" ? "흑 승" : "백 승";
  }, [gameOver]);

  return (
    <div className="min-h-screen p-4 md:p-8 bg-stone-50">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={onHomeClick}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 홈
          </button>
          <div className="text-xs text-stone-500">
            {connected ? "연결됨" : "연결 중..."} · {gameId}
          </div>
        </div>

        <div className="grid md:grid-cols-[1fr_280px] gap-6">
          <div className="flex justify-center">
            <Board
              stones={state?.stones ?? []}
              lastMove={lastMove}
              forbiddenSquares={forbidden}
              toMove={toMove}
              hoverColor={
                state && state.status !== "OVER" && myTurn ? toMove : null
              }
              disabled={disabled}
              onPlay={onPlay}
            />
          </div>

          <div className="space-y-4">
            {state && (
              <>
                <div className="space-y-2">
                  <div className="flex justify-between items-center bg-white rounded-md border border-stone-200 p-3">
                    <PlayerLine info={whitePlayer} />
                    <Clock
                      color="WHITE"
                      snap={state.clocks.white}
                      active={state.to_move === "WHITE" && state.status === "IN_PROGRESS"}
                      serverTimeMs={state.server_time_ms}
                    />
                  </div>
                  <div className="flex justify-between items-center bg-white rounded-md border border-stone-200 p-3">
                    <PlayerLine info={blackPlayer} />
                    <Clock
                      color="BLACK"
                      snap={state.clocks.black}
                      active={state.to_move === "BLACK" && state.status === "IN_PROGRESS"}
                      serverTimeMs={state.server_time_ms}
                    />
                  </div>
                </div>

                <div className="bg-white rounded-md border border-stone-200 p-3 text-sm">
                  <div className="text-stone-500">현재 수</div>
                  <div className="font-mono text-lg">
                    {state.move_number} · {state.to_move === "BLACK" ? "흑" : "백"} 차례
                  </div>
                  {myColor && myColor !== "BOTH" && (
                    <div className="text-xs text-stone-500 mt-1">
                      내 색: {myColor === "BLACK" ? "흑" : "백"}{" "}
                      {myTurn ? (
                        <span className="text-green-600">(내 차례)</span>
                      ) : (
                        <span className="text-stone-400">(대기)</span>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={onResign}
                  disabled={state.status === "OVER"}
                  className="w-full py-2 border border-red-300 text-red-600 rounded hover:bg-red-50 disabled:opacity-50"
                >
                  기권
                </button>

                <Chat
                  title="채팅"
                  messages={chat}
                  onSend={sendChat}
                  disabled={!connected}
                  size="sm"
                />
              </>
            )}
          </div>
        </div>
      </div>

      {pendingExit !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-30">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full space-y-4">
            <h2 className="text-lg font-bold">게임을 나가시겠어요?</h2>
            <p className="text-sm text-stone-600 leading-relaxed">
              지금 나가면 <strong className="text-red-600">기권 처리</strong>되어
              상대에게 승리가 기록됩니다.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPendingExit(null)}
                className="flex-1 py-2 border border-stone-300 rounded text-stone-700 hover:bg-stone-50"
              >
                계속 둘게요
              </button>
              <button
                onClick={confirmLeaveAndResign}
                className="flex-1 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                나가기 (기권)
              </button>
            </div>
          </div>
        </div>
      )}

      {gameOver && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
            <h2 className="text-2xl font-bold mb-2">게임 종료</h2>
            <div className="text-lg text-stone-700 mb-4">
              {winnerText} · {REASON_LABEL[gameOver.reason]}
            </div>
            {gameOver.backToRoom && countdown !== null && (
              <div className="text-sm text-stone-500 mb-4">
                {countdown}초 후 방으로 돌아갑니다.
              </div>
            )}
            <div className="flex flex-col gap-2">
              {gameOver.backToRoom ? (
                <button
                  onClick={() => navigate(`/rooms/${gameOver.backToRoom}`)}
                  className="py-2 bg-stone-900 text-white rounded"
                >
                  방으로 돌아가기
                </button>
              ) : (
                <button
                  onClick={() => navigate("/lobby")}
                  className="py-2 bg-stone-900 text-white rounded"
                >
                  로비로
                </button>
              )}
              {gameOver.matchId !== null && (
                <button
                  onClick={() => navigate(`/matches/${gameOver.matchId}`)}
                  className="py-2 border border-stone-300 text-stone-700 rounded hover:bg-stone-50"
                >
                  기보 다시 보기
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
