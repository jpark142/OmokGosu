"""Unit tests for the profanity / sexual content blur filter."""
from __future__ import annotations

from omok_server.services.chat_filter import should_blur


def test_plain_korean_passes() -> None:
    assert not should_blur("안녕하세요 반가워요")
    assert not should_blur("좋은 수네요 ㅎㅎ")
    assert not should_blur("한 판 더 가시죠")


def test_plain_english_passes() -> None:
    assert not should_blur("nice move")
    assert not should_blur("gg wp")
    assert not should_blur("hello there")


def test_korean_profanity_flagged() -> None:
    assert should_blur("시발")
    assert should_blur("씨발")
    assert should_blur("ㅅㅂ")
    assert should_blur("병신")
    assert should_blur("개새끼")


def test_english_profanity_flagged() -> None:
    assert should_blur("fuck")
    assert should_blur("you shit")
    assert should_blur("asshole behavior")


def test_sexual_terms_flagged() -> None:
    assert should_blur("야동 보자")
    assert should_blur("자위")
    assert should_blur("porn")


def test_normalization_defeats_simple_spacing() -> None:
    # Spaces and ASCII punctuation between letters are stripped before matching.
    assert should_blur("시 발")
    assert should_blur("시.발")
    assert should_blur("f u c k")
    assert should_blur("fuck!!!")


def test_case_insensitive_for_english() -> None:
    assert should_blur("FUCK")
    assert should_blur("ShIt")


def test_empty_input_safe() -> None:
    assert not should_blur("")
    assert not should_blur("   ")


def test_substring_inside_word_can_match() -> None:
    # Document the current behavior: a bad token embedded in a longer word
    # still trips the filter. False positives are acceptable here for a small
    # word list; tuning would mean accepting more false negatives.
    assert should_blur("ass-something")  # contains "ass"
    assert should_blur("그건 시발점이야")  # contains "시발"
