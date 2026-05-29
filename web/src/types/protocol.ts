// Mirrors server/omok_server/schemas.py. Update both together.

export type ColorStr = "BLACK" | "WHITE";
export type GameMode = "hvh" | "hva";
export type AILevel = "random" | "smart" | "minimax" | "heuristic" | "alphazero";
export type GameStatus = "IN_PROGRESS" | "OVER";
export type GameOverReason = "FIVE" | "OVERLINE_WIN" | "RESIGN" | "TIMEOUT";
export type ForbiddenReason =
  | "DOUBLE_THREE"
  | "DOUBLE_FOUR"
  | "OVERLINE"
  | "NOT_YOUR_TURN"
  | "OCCUPIED"
  | "OUT_OF_BOUNDS"
  | "GAME_OVER";
export type PlayerKind = "human" | "ai";

export interface Stone {
  r: number;
  c: number;
  color: ColorStr;
}

export interface PlayerInfo {
  name: string;
  kind: PlayerKind;
  user_id?: number | null;
  wins?: number | null;
  losses?: number | null;
}

// ---------- Auth (Phase 3A) ----------

export interface UserSummary {
  id: number;
  username: string;
  wins: number;
  losses: number;
}

export interface AuthCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: UserSummary;
}

export interface StatsUpdate {
  user_id: number;
  wins: number;
  losses: number;
}

export interface ClockSnapshot {
  main_ms: number;
  byoyomi_periods: number;
  byoyomi_ms: number;
  in_byoyomi: boolean;
}

export interface ClocksSnapshot {
  black: ClockSnapshot;
  white: ClockSnapshot;
}

// ---------- REST ----------

export type AIDifficulty = "easy" | "medium" | "hard";

export interface CreateGameRequest {
  mode: GameMode;
  ai_level?: AILevel;
  ai_difficulty?: AIDifficulty;
  player_name?: string;
}

export interface CreateGameResponse {
  game_id: string;
  your_color: ColorStr;
  ws_url: string;
}

// ---------- WS server → client ----------

export interface SStateMsg {
  type: "state";
  game_id: string;
  board_size: number;
  stones: Stone[];
  to_move: ColorStr;
  move_number: number;
  last_move: Stone | null;
  forbidden_squares: [number, number][];
  clocks: ClocksSnapshot;
  players: Record<ColorStr, PlayerInfo>;
  status: GameStatus;
  server_time_ms: number;
}

export interface SMoveAppliedMsg {
  type: "move_applied";
  move: Stone;
  move_number: number;
  last_move_at_ms: number;
}

export interface STimerTickMsg {
  type: "timer_tick";
  clocks: ClocksSnapshot;
  to_move: ColorStr;
  server_time_ms: number;
}

export interface SForbiddenRejectedMsg {
  type: "forbidden_move_rejected";
  r: number;
  c: number;
  reason: ForbiddenReason;
}

export interface SGameOverMsg {
  type: "game_over";
  winner: ColorStr | null;
  reason: GameOverReason;
  stats_updates?: StatsUpdate[];
  back_to_room?: string | null;
}

export interface SErrorMsg {
  type: "error";
  message: string;
}

export interface SPongMsg {
  type: "pong";
}

export type ServerMsg =
  | SStateMsg
  | SMoveAppliedMsg
  | STimerTickMsg
  | SForbiddenRejectedMsg
  | SGameOverMsg
  | SErrorMsg
  | SPongMsg;

// ---------- WS client → server ----------

export type ClientMsg =
  | { type: "move"; r: number; c: number }
  | { type: "resign"; color?: ColorStr }
  | { type: "ping" };
