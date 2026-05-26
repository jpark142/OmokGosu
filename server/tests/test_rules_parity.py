"""Load the shared C++ fixture file and verify the pybind11 binding matches the
expected verdicts. Detects binding/wrapper drift from the C++ engine.
"""
from __future__ import annotations

import json
import pathlib

import omok_core
import pytest

FIXTURE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "cpp"
    / "tests"
    / "fixtures"
    / "forbidden_positions.json"
)


def _load_fixtures() -> list[dict]:
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file not found at {FIXTURE_PATH}")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _py_color(s: str) -> omok_core.Color:
    return omok_core.Color.Black if s == "BLACK" else omok_core.Color.White


@pytest.mark.parametrize("case", _load_fixtures(), ids=lambda c: c["name"])
def test_fixture_case(case: dict) -> None:
    board = omok_core.Board()
    for stone in case.get("stones", []):
        ok = board.play(stone["r"], stone["c"], _py_color(stone["color"]))
        assert ok, f"Setup play failed at {stone}"

    r = case["candidate"]["r"]
    c = case["candidate"]["c"]
    candidate_color = _py_color(case.get("candidate_color", "BLACK"))
    expected = case["expected"]

    rc = omok_core.RuleChecker()

    if expected == "FIVE_WIN":
        assert rc.is_winning_move(board, r, c, candidate_color), case["name"]
        return

    if expected == "LEGAL":
        if candidate_color == omok_core.Color.Black:
            assert rc.classify_for_black(board, r, c) == omok_core.ForbiddenKind.Nothing
        # White can play anything that's empty; the test asserts no exception.
        return

    if candidate_color != omok_core.Color.Black:
        pytest.fail(f"Non-LEGAL/FIVE_WIN expected but candidate is white: {case['name']}")

    kind = rc.classify_for_black(board, r, c)
    expected_kind_map = {
        "DOUBLE_THREE": omok_core.ForbiddenKind.DoubleThree,
        "DOUBLE_FOUR": omok_core.ForbiddenKind.DoubleFour,
        "OVERLINE": omok_core.ForbiddenKind.Overline,
    }
    assert kind == expected_kind_map[expected], (
        f"{case['name']}: expected {expected}, got {kind}"
    )
