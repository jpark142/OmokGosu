"""SQLite + SQLModel layer for persistent OmokGosu data (users, match history).

Rooms are NOT persisted here — they live only in RoomManager (in-memory) and
disappear on server restart. See docs/AI.md Phase 3 plan.
"""
