"""Unit tests for username_rules.validate_username."""
from __future__ import annotations

import pytest

from omok_server.auth.username_rules import (
    MAX_USERNAME_WIDTH,
    MIN_USERNAME_WIDTH,
    UsernameError,
    validate_username,
    width,
)


# ----- width -----

def test_width_latin_is_one_per_char() -> None:
    assert width("abc") == 3
    assert width("abcdef123456") == 12


def test_width_korean_is_two_per_char() -> None:
    assert width("가") == 2
    assert width("가나다") == 6
    assert width("가나다라마바") == 12


def test_width_mixed_adds_up() -> None:
    assert width("가b가") == 5
    assert width("가나ab") == 6


def test_width_jamo_counts_as_two() -> None:
    # "ㅋㅋ" reads as Korean width.
    assert width("ㅋㅋ") == 4


# ----- valid usernames -----

def test_valid_korean_6_chars() -> None:
    assert validate_username("가나다라마바") == "가나다라마바"


def test_valid_latin_12_chars() -> None:
    assert validate_username("abcdef123456") == "abcdef123456"


def test_valid_mixed_under_budget() -> None:
    # 1 Korean (=2) + 4 Latin (=4) = width 6, code points 5 → fine
    assert validate_username("가abcd") == "가abcd"


def test_valid_jamo_only() -> None:
    # 6 jamo = width 12 — at the edge
    assert validate_username("ㅋㅋㅋㅋㅋㅋ") == "ㅋㅋㅋㅋㅋㅋ"


def test_whitespace_stripped_then_validated() -> None:
    assert validate_username("  나니  ") == "나니"


# ----- rejected: charset -----

def test_underscore_rejected() -> None:
    with pytest.raises(UsernameError, match="특수문자"):
        validate_username("user_1")


def test_hyphen_rejected() -> None:
    with pytest.raises(UsernameError, match="특수문자"):
        validate_username("user-1")


def test_space_inside_rejected() -> None:
    with pytest.raises(UsernameError, match="특수문자"):
        validate_username("user name")


def test_dot_rejected() -> None:
    with pytest.raises(UsernameError, match="특수문자"):
        validate_username("user.1")


def test_emoji_rejected() -> None:
    with pytest.raises(UsernameError, match="특수문자"):
        validate_username("user🎯")


# ----- rejected: length / width -----

def test_korean_1_char_rejected() -> None:
    # 1 Korean char = width 2, below the 4-unit floor
    with pytest.raises(UsernameError, match="이상"):
        validate_username("가")


def test_latin_3_chars_rejected() -> None:
    # 3 Latin chars = width 3, below the 4-unit floor
    with pytest.raises(UsernameError, match="이상"):
        validate_username("abc")


def test_korean_2_chars_passes() -> None:
    assert width("가나") == MIN_USERNAME_WIDTH
    validate_username("가나")


def test_latin_4_chars_passes() -> None:
    assert width("abcd") == MIN_USERNAME_WIDTH
    validate_username("abcd")


def test_korean_7_chars_rejected() -> None:
    with pytest.raises(UsernameError, match="6자"):
        validate_username("가나다라마바사")  # width 14


def test_latin_13_chars_rejected() -> None:
    # Pydantic schema also caps at 12 code points, but if the call bypasses
    # the model and goes straight to validate_username (as our tests do here)
    # the validator still rejects on width.
    with pytest.raises(UsernameError, match="12자"):
        validate_username("abcdef1234567")  # width 13


def test_at_max_boundary_passes() -> None:
    assert width("abcdef123456") == MAX_USERNAME_WIDTH
    validate_username("abcdef123456")


# ----- empty / None-like -----

def test_empty_string_rejected() -> None:
    with pytest.raises(UsernameError, match="이상"):
        validate_username("")


def test_whitespace_only_rejected() -> None:
    with pytest.raises(UsernameError, match="이상"):
        validate_username("   ")
