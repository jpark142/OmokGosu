"""Operator (운영자) registry.

A small, config-driven list of usernames that the UI flags with a "운영자"
badge so official accounts are recognizable. Source of truth is the
`OMOK_OPERATOR_USERNAMES` env var (comma-separated); it defaults to the single
seed operator so the feature works out of the box without extra config.

Matching is case-insensitive, consistent with case-insensitive username
uniqueness. The list is read once at import — change the env + restart to
update.
"""
from __future__ import annotations

import os

_DEFAULT = "운영자"


def _load() -> list[str]:
    raw = os.environ.get("OMOK_OPERATOR_USERNAMES", _DEFAULT)
    seen: dict[str, str] = {}
    for part in raw.split(","):
        name = part.strip()
        if name:
            seen.setdefault(name.lower(), name)  # de-dupe case-insensitively
    return list(seen.values())


_OPERATORS: list[str] = _load()
_OPERATOR_KEYS: frozenset[str] = frozenset(n.lower() for n in _OPERATORS)


def operator_usernames() -> list[str]:
    """The configured operator usernames, in their display form."""
    return list(_OPERATORS)


def is_operator(username: str | None) -> bool:
    """True if `username` matches a configured operator (case-insensitive)."""
    return bool(username) and username.strip().lower() in _OPERATOR_KEYS
