"""Username validation.

Allowed characters: complete Hangul syllables (가-힣), Latin letters, and
digits. No spaces, no punctuation, no emoji — and no standalone Hangul jamo
(ㄱ-ㅎ / ㅏ-ㅣ) anywhere in the name. Banning jamo outright blocks both
jamo-only names ("ㅋㅋ", "ㅗㅗ") and mixed sloppy ones ("이ㅇ", "크크ㅋ") with a
single rule. Names are also screened against the chat profanity filter.

Width limit: treats Korean / CJK characters as 2 display units and
Latin / digits as 1 unit. With a budget of `MAX_USERNAME_WIDTH = 12`,
that maps onto common Korean web conventions of "6 Korean chars or 12
English chars" — they consume the same horizontal space in chat,
leaderboard rows, profile cards.
"""
from __future__ import annotations

import re
import unicodedata

from omok_server.services.chat_filter import should_blur

MIN_USERNAME_WIDTH = 4        # display-width units  (= 2 Korean chars or 4 Latin)
MAX_USERNAME_WIDTH = 12       # display-width units  (= 6 Korean chars or 12 Latin)

# Only complete Hangul syllables, Latin letters, and digits — no bare jamo.
_ALLOWED_RE = re.compile(r"^[0-9A-Za-z가-힣]+$")


class UsernameError(ValueError):
    """Raised when a candidate username fails validation. The message is
    user-facing Korean text intended to surface directly to the registrant."""


def _char_width(ch: str) -> int:
    """1 for Latin/digits, 2 for CJK syllables/jamo (East Asian Wide/Full)."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def width(name: str) -> int:
    """Total display width of `name` under the 1-unit / 2-unit rule."""
    return sum(_char_width(ch) for ch in name)


def validate_username(raw: str) -> str:
    """Normalize and validate a candidate username; return the cleaned form.

    Raises `UsernameError` with a Korean message describing the first failed
    rule. The cleaned form is `raw.strip()` — no other normalization (no
    case folding, no NFC; users see exactly what they typed).
    """
    name = (raw or "").strip()

    # Charset first so a name like "_" gets the charset message, not the
    # too-short message — clearer to the user.
    if not name:
        raise UsernameError("닉네임은 한글 2자 (또는 영문·숫자 4자) 이상이어야 합니다")

    if not _ALLOWED_RE.match(name):
        raise UsernameError(
            "닉네임은 한글·영문·숫자만 사용할 수 있습니다 "
            "(단독 자음·모음 ㄱㅏ, 공백·특수문자 불가)"
        )

    if should_blur(name):
        raise UsernameError("사용할 수 없는 닉네임입니다 (부적절한 표현이 포함되어 있습니다)")

    w = width(name)
    if w < MIN_USERNAME_WIDTH:
        raise UsernameError("닉네임은 한글 2자 (또는 영문·숫자 4자) 이상이어야 합니다")
    if w > MAX_USERNAME_WIDTH:
        raise UsernameError("닉네임은 한글 6자 (또는 영문·숫자 12자) 까지만 가능합니다")

    return name
