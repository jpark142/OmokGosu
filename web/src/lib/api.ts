import { http } from "@/lib/fetcher";
import type {
  CreateGameRequest,
  CreateGameResponse,
  CreateRoomReq,
  JoinRoomReq,
  RecentMatches,
  RoomDetail,
  RoomSummary,
  SStateMsg,
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
