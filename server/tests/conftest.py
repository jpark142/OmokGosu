"""Shared pytest fixtures.

Sets OMOK_DB_PATH to a temp file BEFORE any omok_server import so the SQLite
engine binds to a throwaway file rather than the real `data/omok.sqlite`.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

# These must run before omok_server is imported anywhere (engine.py reads
# OMOK_DB_PATH at module import time).
_TMP_DIR = Path(tempfile.mkdtemp(prefix="omok-tests-"))
os.environ["OMOK_DB_PATH"] = str(_TMP_DIR / "test.sqlite")
os.environ.setdefault(
    "OMOK_JWT_SECRET", "omok-test-secret-must-be-at-least-32-bytes-long"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from omok_server.api import chat as _chat_helpers  # noqa: E402
from omok_server.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_chat_state():
    """Chat buffers + rate-limit state are process-global. Wipe between tests
    so a system message emitted by one test doesn't show up in another's
    chat_history (which would derail WS receive sequences)."""
    _chat_helpers.clear_all_buffers()
    yield
    _chat_helpers.clear_all_buffers()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def unique_username(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def auth_client(client: TestClient) -> tuple[TestClient, str, dict]:
    """Register a fresh user and return (client, token, user_dict).

    The client returned has the Authorization header pre-baked so callers can
    just do `client.post(...)` and the token is sent automatically.
    """
    username = unique_username()
    r = client.post("/api/auth/register", json={"username": username, "password": "pw1234"})
    assert r.status_code == 201, r.text
    data = r.json()
    token = data["access_token"]
    user = data["user"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, token, user
