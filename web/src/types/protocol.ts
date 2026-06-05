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
  current_room_id?: string | null;  // set on /me when user is in a room
}

export interface MatchSummary {
  match_id: number;
  opponent_username: string | null;
  opponent_user_id: number | null;
  your_color: ColorStr;
  you_won: boolean;
  over_reason: GameOverReason;
  is_ai_game: boolean;
  ended_at: number;  // unix seconds
  move_count: number;
}

export interface RecentMatches {
  user_id: number;
  matches: MatchSummary[];
}

export interface MatchDetail {
  match_id: number;
  game_id: string;
  black_username: string | null;
  white_username: string | null;
  winner_color: ColorStr | null;
  over_reason: GameOverReason;
  is_ai_game: boolean;
  started_at: number;
  ended_at: number;
  move_count: number;
  moves: Stone[];
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

// ---------- Rooms (Phase 3B) ----------

export type RoomStatusStr = "LOBBY" | "PLAYING";

export interface RoomMemberSummary {
  user_id: number;
  username: string;
  wins: number;
  losses: number;
}

export interface RoomSummary {
  room_id: string;
  title: string;
  has_password: boolean;
  host: RoomMemberSummary;
  guest: RoomMemberSummary | null;
  status: RoomStatusStr;
  created_at: number;
}

export interface RoomDetail extends RoomSummary {
  guest_ready: boolean;
  current_game_id: string | null;
  games_played: number;
}

export interface CreateRoomReq {
  title: string;
  password?: string | null;
}

export interface JoinRoomReq {
  password?: string | null;
}

// Room WS (client → server)
export type ClientRoomMsg =
  | { type: "ready"; value: boolean }
  | { type: "start" }
  | { type: "leave" }
  | { type: "ping" };

// Room WS (server → client)
export type ServerRoomMsg =
  | { type: "room_state"; room: RoomDetail }
  | { type: "room_game_started"; game_id: string }
  | { type: "room_closed"; reason: "host_left" | "kicked" }
  | { type: "error"; message: string }
  | { type: "pong" };

// Lobby WS (server → client only — client just keepalive pings)
export type ServerLobbyMsg =
  | { type: "lobby_snapshot"; rooms: RoomSummary[] }
  | {
      type: "lobby_update";
      action: "created" | "updated" | "removed";
      room_id: string;
      room: RoomSummary | null;
    }
  | { type: "pong" };

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
  match_id?: number | null;
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
