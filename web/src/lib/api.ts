import { http } from "@/lib/fetcher";
import type {
  CreateGameRequest,
  CreateGameResponse,
  SStateMsg,
} from "@/types/protocol";

export function createGame(req: CreateGameRequest): Promise<CreateGameResponse> {
  return http.post<CreateGameResponse>("/api/games", req as unknown as Record<string, unknown>);
}

export function getGame(gameId: string): Promise<SStateMsg> {
  return http.get<SStateMsg>(`/api/games/${gameId}`);
}
