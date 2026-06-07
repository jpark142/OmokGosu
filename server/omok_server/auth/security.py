"""Password hashing (bcrypt) and JWT encode/decode.

JWT secret comes from the OMOK_JWT_SECRET env var. If unset, a fixed dev
default is used and a warning is logged — fine for local dev but unsafe for
deployed servers.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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


def create_access_token(
    user_id: int, token_version: int = 0, extra: Optional[dict] = None
) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "ver": int(token_version),
        "iat": int(now.timestamp()),
        "exp": int((now + _TOKEN_TTL).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)


class TokenError(Exception):
    """Token missing, malformed, or expired."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    # `ver` matches User.token_version at issue time. Auth deps compare this
    # to the current DB value; mismatch means the user logged in elsewhere
    # since this token was issued and we should reject it.
    ver: int


def decode_access_token(token: str) -> TokenPayload:
    """Return decoded token payload, or raise TokenError."""
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
        user_id = int(sub)
    except (TypeError, ValueError) as e:
        raise TokenError("token sub not an int") from e
    # Tokens issued before the token_version mechanism existed have no `ver`
    # claim; treat as 0 so they still authenticate against fresh users
    # (token_version starts at 0). Once such a user logs in again, the
    # bump to 1 will retire any lingering old tokens.
    ver_raw = payload.get("ver", 0)
    try:
        ver = int(ver_raw)
    except (TypeError, ValueError) as e:
        raise TokenError("token ver not an int") from e
    return TokenPayload(user_id=user_id, ver=ver)
