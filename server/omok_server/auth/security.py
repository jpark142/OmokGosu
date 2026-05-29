"""Password hashing (bcrypt) and JWT encode/decode.

JWT secret comes from the OMOK_JWT_SECRET env var. If unset, a fixed dev
default is used and a warning is logged — fine for local dev but unsafe for
deployed servers.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

_log = logging.getLogger(__name__)

_DEV_DEFAULT_SECRET = "omok-dev-secret-change-me-for-production-32b"  # noqa: S105
_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(days=7)


def _get_secret() -> str:
    secret = os.environ.get("OMOK_JWT_SECRET")
    if not secret:
        _log.warning(
            "OMOK_JWT_SECRET not set — using insecure dev default. Set this in production."
        )
        return _DEV_DEFAULT_SECRET
    return secret


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("password must not be empty")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash → treat as failure rather than crashing the request.
        return False


def create_access_token(user_id: int, extra: Optional[dict] = None) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + _TOKEN_TTL).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)


class TokenError(Exception):
    """Token missing, malformed, or expired."""


def decode_access_token(token: str) -> int:
    """Return user_id encoded in the token, or raise TokenError."""
    if not token:
        raise TokenError("missing token")
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError(f"invalid token: {e}") from e
    sub = payload.get("sub")
    if sub is None:
        raise TokenError("token missing sub claim")
    try:
        return int(sub)
    except (TypeError, ValueError) as e:
        raise TokenError("token sub not an int") from e
