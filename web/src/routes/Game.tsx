import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import Board from "@/components/Board";
import Chat from "@/components/Chat";
import Clock from "@/components/Clock";
import ParticipantsPanel from "@/components/ParticipantsPanel";
import { useGameSocket } from "@/hooks/useGameSocket";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/fetcher";
import { playMoveSound, speak } from "@/lib/sound";
import { useVersion } from "@/lib/versionContext";
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
  DRAW: "판 가득 (무승부)",
  ABORTED: "무효 (대국 시작 전 기권)",
};

function PlayerLine({ info }: { info: PlayerInfo | undefined }) {
  if (!info) return <span className="text-stone-400">—</span>;
  return (
    <div>
      <div className="text-xs uppercase text-stone-500">
        {info.kind === "ai" ? "AI" : "Player"}
      </div>
      <div className="font-medium">{info.name}</div>
    </div>
  );
}

export default function Game() {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const { user, applyStats } = useAuth();
  const { devMode } = useVersion();
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
          if (mine) applyStats(mine.wins, mine.losses, mine.draws);
        }
      } else if (msg.type === "error") {
        toast.error(msg.message);
      }
    });
    return unsub;
  }, [onMessage, user, applyStats]);

  const blackPlayer = state?.players.BLACK;
  const whitePlayer = state?.players.WHITE;
  const spectators = state?.spectators ?? [];

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

  // Spectator iff I'm connected to a game where neither player slot is me.
  // A player joining mid-game gets myColor set; everyone else lands here and
  // sees a read-only board with chat.
  const isSpectator = !!user && !!state && myColor === null;

  // If the game was hosted by a room, auto-return after 5s.
  // Spectators are *not* in the room, so the auto-return doesn't apply to
  // them — they stay on the result screen and leave by hand.
  useEffect(() => {
    if (!gameOver?.backToRoom) return;
    if (isSpectator) return;
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
  }, [gameOver, navigate, isSpectator]);

  const lastMove = state?.last_move ?? null;
  const forbidden = state?.forbidden_squares ?? [];
  const toMove = state?.to_move ?? "BLACK";
  const myTurn =
    !isSpectator && myColor !== null && (myColor === "BOTH" || myColor === toMove);
  const disabled = isSpectator || !state || state.status === "OVER" || !connected || !myTurn;

  // ----- audio effects -----
  // Move click: ring the synthesized "thock" every time a stone is added.
  // The first state snapshot (which may already contain moves from a game
  // joined in progress) initializes the ref without playing, so a viewer
  // doesn't get a barrage of clicks on join.
  const prevMoveCount = useRef<number | null>(null);
  useEffect(() => {
    const count = state?.stones.length ?? 0;
    if (prevMoveCount.current !== null && count > prevMoveCount.current) {
      playMoveSound();
    }
    prevMoveCount.current = count;
  }, [state?.stones.length]);

  // Byo-yomi countdown + period transitions for the active side. Speak only
  // when it's the local player's turn so opponents' clock isn't narrated
  // into the player's ears (distracting + redundant).
  //
  // Two pieces of timing care:
  //   - Each speak() cancels what's pending so the spoken second always
  //     matches the on-screen clock (no queue drift behind a 1s
  //     announcement).
  //   - Period-transition announcements ("마지막입니다", "N번 남았습니다")
  //     are protected by a ~1.3s grace window: during that window the
  //     countdown speak() is skipped so the announcement plays through
  //     instead of being cancelled by the next number. After the grace,
  //     the countdown resumes at whatever the current clock actually
  //     reads — drift-free.
  // Byo-yomi audio is split into two effects:
  //   (a) state-driven: byo-yomi entry + period-transition announcements.
  //       Fire once per state change.
  //   (b) interval-driven (100ms): the actual "십, 구, 팔, ..." countdown.
  //       Must run at the same cadence as the Clock UI (also 100ms) so
  //       the spoken second lands at the exact instant the on-screen
  //       number transitions, not 250ms later when the next server tick
  //       lands. Uses Date.now() - state.server_time_ms to compute the
  //       live byoyomi_ms instead of the stale snapshot value.
  const lastSpokenSecond = useRef<number | null>(null);
  const prevPeriods = useRef<number | null>(null);
  const wasInByoyomi = useRef<boolean | null>(null);
  const announcingUntilMs = useRef<number>(0);

  // Refs so the 100ms interval below always sees the latest values
  // without remounting itself every tick.
  const stateRef = useRef(state);
  stateRef.current = state;
  const myTurnRef = useRef(myTurn);
  myTurnRef.current = myTurn;
  const toMoveRef = useRef(toMove);
  toMoveRef.current = toMove;

  // (a) state-driven announcements
  useEffect(() => {
    if (!state || state.status === "OVER" || !myTurn) {
      lastSpokenSecond.current = null;
      wasInByoyomi.current = null;
      prevPeriods.current = null;
      return;
    }
    const clock = toMove === "BLACK" ? state.clocks.black : state.clocks.white;
    const nowMs = Date.now();

    if (!clock.in_byoyomi) {
      prevPeriods.current = clock.byoyomi_periods;
      lastSpokenSecond.current = null;
      wasInByoyomi.current = false;
      return;
    }
    if (wasInByoyomi.current === false) {
      speak("초읽기를 시작합니다");
      announcingUntilMs.current = nowMs + 1700;
      lastSpokenSecond.current = null;
    }
    wasInByoyomi.current = true;

    const periods = clock.byoyomi_periods;
    if (prevPeriods.current !== null && periods < prevPeriods.current) {
      if (periods === 1) speak("마지막입니다");
      else if (periods > 0) speak(`${periods}번 남았습니다`);
      announcingUntilMs.current = Math.max(announcingUntilMs.current, nowMs + 1300);
      lastSpokenSecond.current = null;
    }
    prevPeriods.current = periods;
  }, [state, myTurn, toMove]);

  // (b) 100ms countdown driver
  useEffect(() => {
    const KO_NUMBER: Record<number, string> = {
      1: "일", 2: "이", 3: "삼", 4: "사", 5: "오",
      6: "육", 7: "칠", 8: "팔", 9: "구", 10: "십",
    };
    const id = window.setInterval(() => {
      const s = stateRef.current;
      if (!s || s.status === "OVER" || !myTurnRef.current) return;
      const clock = toMoveRef.current === "BLACK" ? s.clocks.black : s.clocks.white;
      if (!clock.in_byoyomi) return;
      const nowMs = Date.now();
      if (nowMs < announcingUntilMs.current) return;

      // Live byoyomi_ms = snapshot minus time elapsed since that snapshot
      // arrived. Matches the Clock component's own deduction so the
      // spoken second aligns with the on-screen transition.
      const localElapsed = Math.max(0, nowMs - s.server_time_ms);
      const liveByoyomiMs = Math.max(0, clock.byoyomi_ms - localElapsed);
      const secondsLeft = Math.ceil(liveByoyomiMs / 1000);

      if (
        secondsLeft > 0 &&
        secondsLeft <= 10 &&
        secondsLeft !== lastSpokenSecond.current
      ) {
        lastSpokenSecond.current = secondsLeft;
        speak(KO_NUMBER[secondsLeft] ?? String(secondsLeft));
      }
    }, 100);
    return () => window.clearInterval(id);
  }, []);

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
  // button just navigates (no resignation needed). Spectators skip the
  // confirm modal entirely — they have nothing to forfeit.
  const onHomeClick = () => {
    if (isSpectator || !state || state.status === "OVER") {
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
    if (gameOver.reason === "ABORTED") return "무효";
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
          <div className="flex items-center gap-2 text-xs text-stone-500">
            {isSpectator && (
              <span className="px-2 py-0.5 rounded bg-sky-100 text-sky-700 font-medium">
                관전 중
              </span>
            )}
            <span>{connected ? "연결됨" : "연결 중..."} · {gameId}</span>
            {devMode && gameId && (
              <button
                onClick={async () => {
                  try {
                    await http.post(`/api/games/${gameId}/_dev/clip-clock`);
                    toast.success("시계 10초로 단축");
                  } catch {
                    toast.error("DEV 치트 실패");
                  }
                }}
                className="ml-2 px-2 py-0.5 rounded border border-purple-300 bg-purple-50 text-purple-700 font-medium hover:bg-purple-100"
                title="양쪽 main 시간을 10초로 단축 (byo-yomi 흐름 테스트용)"
              >
                DEV: 시계 10초
              </button>
            )}
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

                <ParticipantsPanel
                  blackPlayer={blackPlayer}
                  whitePlayer={whitePlayer}
                  spectators={spectators}
                />

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

                {!isSpectator && (
                  <button
                    onClick={onResign}
                    disabled={state.status === "OVER"}
                    className="w-full py-2 border border-red-300 text-red-600 rounded hover:bg-red-50 disabled:opacity-50"
                  >
                    기권
                  </button>
                )}

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
            {!isSpectator && gameOver.backToRoom && countdown !== null && (
              <div className="text-sm text-stone-500 mb-4">
                {countdown}초 후 방으로 돌아갑니다.
              </div>
            )}
            <div className="flex flex-col gap-2">
              {isSpectator ? (
                <>
                  <button
                    onClick={() => navigate("/lobby")}
                    className="py-2 bg-stone-900 text-white rounded"
                  >
                    로비로
                  </button>
                  <button
                    onClick={() => setGameOver(null)}
                    className="py-2 border border-stone-300 text-stone-700 rounded hover:bg-stone-50"
                  >
                    계속 보기
                  </button>
                </>
              ) : gameOver.backToRoom ? (
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
