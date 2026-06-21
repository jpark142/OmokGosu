"""Unit tests for the profanity / sexual content mask filter."""
from __future__ import annotations

from omok_server.services.chat_filter import mask_bad_words, should_blur


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


# ----- mask_bad_words: what the chat pipeline actually applies -----

def test_mask_replaces_bad_word_with_asterisks_same_length() -> None:
    assert mask_bad_words("시발") == "**"
    assert mask_bad_words("fuck") == "****"
    assert mask_bad_words("ㅅㅂ") == "**"


def test_mask_preserves_surrounding_text_and_spaces() -> None:
    assert mask_bad_words("이 시발 진짜") == "이 ** 진짜"
    assert mask_bad_words("you fuck this") == "you **** this"


def test_mask_keeps_whitespace_inside_obfuscated_word() -> None:
    # "시 발" detects via normalization but only the two letter positions
    # are masked — the space between them is preserved.
    assert mask_bad_words("시 발") == "* *"
    assert mask_bad_words("f u c k") == "* * * *"


def test_mask_keeps_punctuation_after_bad_word() -> None:
    assert mask_bad_words("fuck!!!") == "****!!!"
    assert mask_bad_words("시발.") == "**."


def test_mask_handles_multiple_bad_words_in_one_message() -> None:
    out = mask_bad_words("fuck and shit")
    assert "fuck" not in out
    assert "shit" not in out
    assert "and" in out
    assert out == "**** and ****"


def test_mask_is_case_insensitive() -> None:
    # Detection is case-insensitive; surrounding text keeps its case.
    # "FUCKing" matches *both* "fuck" and "fucking" entries in the list,
    # so the union of their character spans is masked (all 7 letters).
    assert mask_bad_words("Stop FUCKing around") == "Stop ******* around"
    assert mask_bad_words("Hello SHIT world") == "Hello **** world"


def test_mask_passes_through_clean_text_unchanged() -> None:
    text = "안녕하세요 반가워요"
    assert mask_bad_words(text) == text
    assert mask_bad_words("nice move") == "nice move"


def test_mask_empty_input_is_identity() -> None:
    assert mask_bad_words("") == ""
