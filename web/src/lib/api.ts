import type {
  CreateGameRequest,
  CreateGameResponse,
  SStateMsg,
} from "@/types/protocol";

const BASE = ""; // Vite proxies /api → :8000 in dev.

export async function createGame(req: CreateGameRequest): Promise<CreateGameResponse> {
  const r = await fetch(`${BASE}/api/games`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`createGame failed: ${r.status}`);
  return r.json();
}

export async function getGame(gameId: string): Promise<SStateMsg> {
  const r = await fetch(`${BASE}/api/games/${gameId}`);
  if (!r.ok) throw new Error(`getGame failed: ${r.status}`);
  return r.json();
}
