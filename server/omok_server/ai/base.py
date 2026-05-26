"""AI player protocol.

Each concrete AI (random, minimax, heuristic, alphazero) implements this. The
session loop in ws.py will instantiate the right one for HVA games and call
`choose_move` when it is the AI's turn.
"""
from __future__ import annotations

from typing import Protocol

from omok_server.game.engine import Engine
from omok_server.schemas import ColorStr


class AIPlayer(Protocol):
    name: str

    def choose_move(self, engine: Engine, color: ColorStr, budget_ms: int) -> tuple[int, int]:
        """Return (r, c) for the next move within roughly `budget_ms` of compute."""
        ...
