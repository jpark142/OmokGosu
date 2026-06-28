import { http } from "@/lib/fetcher";
import type {
  CreateGameRequest,
  CreateGameResponse,
  CreateRoomReq,
  JoinRoomReq,
  Leaderboard,
  MatchDetail,
  RecentMatches,
  RoomDetail,
  RoomSummary,
  SStateMsg,
  UserSummary,
} from "@/types/protocol";

export function createGame(req: CreateGameRequest): Promise<CreateGameResponse> {
  return http.post<CreateGameResponse>("/api/games", req as unknown as Record<string, unknown>);
}

export function getGame(gameId: string): Promise<SStateMsg> {
  return http.get<SStateMsg>(`/api/games/${gameId}`);
}

// ---------- Rooms ----------

export function listRooms(): Promise<RoomSummary[]> {
  return http.get<RoomSummary[]>("/api/rooms");
}

export function createRoom(req: CreateRoomReq): Promise<RoomDetail> {
  return http.post<RoomDetail>("/api/rooms", req as unknown as Record<string, unknown>);
}

export function getRoom(id: string): Promise<RoomDetail> {
  return http.get<RoomDetail>(`/api/rooms/${id}`);
}

export function joinRoom(id: string, req: JoinRoomReq): Promise<RoomDetail> {
  return http.post<RoomDetail>(`/api/rooms/${id}/join`, req as unknown as Record<string, unknown>);
}

export function leaveRoom(id: string): Promise<void> {
  return http.post<void>(`/api/rooms/${id}/leave`);
}

export function getRecentMatches(userId: number, limit = 5): Promise<RecentMatches> {
  return http.get<RecentMatches>(`/api/users/${userId}/recent-matches?limit=${limit}`);
}

export function getMatch(matchId: number): Promise<MatchDetail> {
  return http.get<MatchDetail>(`/api/matches/${matchId}`);
}

export function getLeaderboard(limit = 20, offset = 0): Promise<Leaderboard> {
  return http.get<Leaderboard>(
    `/api/users/leaderboard?limit=${limit}&offset=${offset}`,
  );
}

export function getUser(userId: number): Promise<UserSummary> {
  return http.get<UserSummary>(`/api/users/${userId}`);
}

// ---------- Bug reports ----------

export interface BugReportRequest {
  description: string;
  url?: string;
  user_agent?: string;
  anonymous?: boolean;
}

export interface BugReportResponse {
  id: number;
  github_issue_number: number | null;
  github_issue_url: string | null;
  mirrored: "github" | "github_failed" | "local_only";
}

export function submitBugReport(req: BugReportRequest): Promise<BugReportResponse> {
  return http.post<BugReportResponse>(
    "/api/bug-reports",
    req as unknown as Record<string, unknown>,
  );
}
