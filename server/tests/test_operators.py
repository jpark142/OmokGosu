"""Operator registry + /api/operators endpoint."""
from __future__ import annotations

from omok_server.services import operators


def test_default_operator_present() -> None:
    # With no OMOK_OPERATOR_USERNAMES override, the seed operator is present.
    assert "운영자" in operators.operator_usernames()


def test_is_operator_is_case_insensitive() -> None:
    assert operators.is_operator("운영자") is True
    assert operators.is_operator("  운영자 ") is True  # trimmed
    assert operators.is_operator("일반유저") is False
    assert operators.is_operator(None) is False
    assert operators.is_operator("") is False


def test_operators_endpoint_public(client) -> None:
    # No auth required — the badge is public info.
    r = client.get("/api/operators")
    assert r.status_code == 200
    assert "운영자" in r.json()["usernames"]
