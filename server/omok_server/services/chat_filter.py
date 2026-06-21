"""Chat content filter — masks profanity / sexual terms with asterisks.

The masked message takes the place of the original on the wire; viewers
never see the offending text. Whitespace and punctuation around the bad
word are preserved so the message structure stays readable:

    "이 시발 진짜"  →  "이 ** 진짜"
    "fuck this"     →  "**** this"
    "시 발"          →  "* *"   (each masked char keeps its raw position)

Detection normalizes (lowercase + strip whitespace and ASCII/Hangul
punctuation) then scans substrings against the word list. This catches
"씨 발", "ㅅ.ㅂ", "fuck!!!" etc. but does NOT defeat full leetspeak
(f4ck) or character substitution (씌발). Good enough for a small
multiplayer friend-and-family deployment.

The word list is intentionally conservative — covers the most common
Korean profanity (often-typed forms + ㅅㅂ-style consonant variants),
English four-letter words, and obvious sexual chat vocabulary. Extend
when operations surface a false negative. False positives are worse
than false negatives here (a masked normal message reads as random
asterisks), so prefer specific terms over broad partial matches.
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


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Same normalization as `_normalize` but also records, for each character
    in the normalized string, the index it came from in the original.

    Returns (normalized, idx_map) where `normalized[i]` originated from
    `text[idx_map[i]]`. Characters dropped by normalization (whitespace,
    punctuation) are absent from both.
    """
    norm_chars: list[str] = []
    idx_map: list[int] = []
    lower = text.lower()
    for i, ch in enumerate(lower):
        if _STRIP_RE.match(ch):
            continue
        norm_chars.append(ch)
        idx_map.append(i)
    return "".join(norm_chars), idx_map


def should_blur(text: str) -> bool:
    """True if the message contains any term in the bad-word list.

    Empty / whitespace-only input returns False. Mainly used by tests and
    by callers that want a boolean signal — `mask_bad_words` is what the
    chat pipeline actually applies before broadcast.
    """
    if not text:
        return False
    norm = _normalize(text)
    if not norm:
        return False
    return any(word in norm for word in _BAD_WORDS)


def mask_bad_words(text: str) -> str:
    """Return `text` with every bad-word occurrence replaced by asterisks.

    Detection runs on the normalized form, but the replacement happens on
    the raw characters so whitespace/punctuation in between letters of an
    obfuscated bad word are kept verbatim:

        "이 시발 진짜" → "이 ** 진짜"
        "f u c k"      → "* * * *"

    If no bad word is present the original string is returned unchanged
    (identity check possible by caller via `result is text`).
    """
    if not text:
        return text
    norm, idx_map = _normalize_with_map(text)
    if not norm:
        return text

    to_mask: set[int] = set()
    for word in _BAD_WORDS:
        if not word:
            continue
        start = 0
        while True:
            pos = norm.find(word, start)
            if pos < 0:
                break
            for j in range(pos, pos + len(word)):
                to_mask.add(idx_map[j])
            # +1 so overlapping bad words are both found ("assfuck" → both
            # "ass" and "fuck" get masked).
            start = pos + 1

    if not to_mask:
        return text
    return "".join("*" if i in to_mask else ch for i, ch in enumerate(text))
