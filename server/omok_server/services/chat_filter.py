"""Chat content filter — flags messages containing profanity or sexual terms.

Marks the message with `is_blurred=True` instead of dropping it; the client
renders blurred text with a click-to-reveal affordance. This preserves the
conversation timeline (other users can still tell who tried to say what,
and a curious viewer can opt in) while making the default view clean.

The word list is intentionally conservative — covers the most common Korean
profanity (often-typed forms + ㅅㅂ-style consonant variants) and English
four-letter words. Sexual terms cover the obvious chat-context ones. Extend
the list when you see false negatives during operation. False positives are
worse than false negatives here (a blurred normal message is confusing), so
prefer specific terms over broad partial matches.

Detection: lowercase + strip whitespace and punctuation, then substring scan.
This catches "씨 발", "ㅅ.ㅂ", "fuck!!!" etc. but does NOT defeat full
leetspeak (f4ck) or character-substitution (씌발). Good enough for a small
multiplayer friend-and-family deployment.
"""
from __future__ import annotations

import re

# ----- word list -----

# Korean profanity. Common consonant-only forms (ㅅㅂ, ㅂㅅ) included on purpose.
_KO_PROFANITY = {
    "씨발", "시발", "씨바", "시바", "ㅅㅂ", "ㅆㅂ",
    "병신", "ㅂㅅ", "븅신",
    "좆", "좃", "ㅈ까", "좆같", "좃같",
    "개새끼", "개색기", "개색끼", "씨발놈", "씨발년", "씹새",
    "지랄", "ㅈㄹ",
    "미친놈", "미친년", "또라이", "또라인",
    "닥쳐",
    "엿먹", "엿이나",
    "ㅗ", "엿같",
    "느금마", "느금", "니애미", "니애비",
}

# English profanity — small set, covers obvious chat use.
_EN_PROFANITY = {
    "fuck", "fucking", "fucker",
    "shit", "bullshit",
    "asshole", "ass",
    "bitch",
    "dick", "cock", "pussy",
    "cunt",
    "motherfucker", "mf",
}

# Sexual/explicit terms — chat-context only. Things you wouldn't shout in a
# game lobby with someone's family looking. Not exhaustive medical vocab.
_SEXUAL = {
    "섹스", "야동", "자위", "딸딸이", "딸치",
    "자지", "보지",
    "ㅅㅅ",
    "sex", "porn", "nude",
}

_BAD_WORDS: frozenset[str] = frozenset(_KO_PROFANITY | _EN_PROFANITY | _SEXUAL)

# Strip whitespace + ASCII punctuation + Korean punctuation for normalization.
# Korean Hangul (가-힣), Hangul jamo (ㄱ-ㅣ), and alphanumerics are kept.
_STRIP_RE = re.compile(r"[\s\.\,\!\?\-\_\*\~\`\@\#\$\%\^\&\(\)\[\]\{\}\<\>\:\;\"\'\\\/]+")


def _normalize(text: str) -> str:
    return _STRIP_RE.sub("", text.lower())


def should_blur(text: str) -> bool:
    """True if the message contains any term in the bad-word list.

    Empty / whitespace-only input returns False (caller should already have
    rejected it as empty before reaching us)."""
    if not text:
        return False
    norm = _normalize(text)
    if not norm:
        return False
    return any(word in norm for word in _BAD_WORDS)
