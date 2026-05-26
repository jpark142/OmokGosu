#include <doctest/doctest.h>

#include "omok/board.hpp"
#include "omok/pattern.hpp"

using namespace omok;
using namespace omok::pattern;

namespace {

// Helper: build a 9-cell line directly. 0=empty, 1=mine, 2=opp, 3=wall.
Line make_line(std::initializer_list<int> cells) {
    Line line;
    int i = 0;
    for (int v : cells) {
        if (i >= Line::LEN) break;
        line.v[i++] = v;
    }
    return line;
}

}  // namespace

TEST_CASE("run_length_through_center: simple single stone") {
    Line line = make_line({0, 0, 0, 0, 1, 0, 0, 0, 0});
    CHECK(run_length_through_center(line) == 1);
}

TEST_CASE("run_length_through_center: five in a row") {
    Line line = make_line({0, 0, 1, 1, 1, 1, 1, 0, 0});
    CHECK(run_length_through_center(line) == 5);
    CHECK(makes_exact_five_through_center(line));
    CHECK(makes_five_or_more_through_center(line));
    CHECK_FALSE(makes_overline_through_center(line));
}

TEST_CASE("run_length_through_center: overline (six)") {
    Line line = make_line({0, 1, 1, 1, 1, 1, 1, 0, 0});
    CHECK(run_length_through_center(line) == 6);
    CHECK_FALSE(makes_exact_five_through_center(line));
    CHECK(makes_overline_through_center(line));
}

TEST_CASE("run_length_through_center: empty center returns 0") {
    Line line = make_line({1, 1, 1, 1, 0, 1, 1, 1, 1});
    CHECK(run_length_through_center(line) == 0);
}

TEST_CASE("line_has_four: open four _BBBB_") {
    Line line = make_line({0, 0, 0, 1, 1, 1, 1, 0, 0});  // mine = positions 3..6, center = 4
    CHECK(line_has_four(line));
}

TEST_CASE("line_has_four: closed four XBBBB_ (wall on left)") {
    Line line = make_line({3, 3, 3, 1, 1, 1, 1, 0, 0});
    CHECK(line_has_four(line));
}

TEST_CASE("line_has_four: broken four BB_BB") {
    // mine positions 2,3, empty 4 is center, mine 5,6 — placing at center makes 5
    // But our function requires center already mine. Let's test the alternative:
    // BB_BB where the center IS one of the mine stones and the gap completes to 5.
    // mine at 3,4(center),5,7 -- placing at 6 makes 5? No, 3,4,5,_,7 → place at 6 makes 3,4,5,6,7 = 5 in row.
    Line line = make_line({0, 0, 0, 1, 1, 1, 0, 1, 0});
    CHECK(line_has_four(line));
}

TEST_CASE("line_has_four: not a four (just three)") {
    Line line = make_line({0, 0, 0, 0, 1, 1, 1, 0, 0});
    CHECK_FALSE(line_has_four(line));
}

TEST_CASE("line_has_naive_open_three: classic _BBB_ shape") {
    // Want: center is part of a 3-run, placing one more makes _BBBB_ (open four).
    // mine at 3,4,5 with both sides empty plenty.
    Line line = make_line({0, 0, 0, 1, 1, 1, 0, 0, 0});
    CHECK(line_has_naive_open_three(line));
}

TEST_CASE("line_has_naive_open_three: closed three _BBB_X is NOT open three") {
    // 3-run with opponent on one side beyond the immediate empty — extending makes closed four not open four.
    Line line = make_line({0, 0, 2, 1, 1, 1, 0, 0, 0});  // opponent at 2, mine 3..5, empty after
    // Placing at 6 makes _BBBB at positions 3-6 but immediate neighbor at 2 is opponent → not open four.
    // Placing at 2... opponent there, can't. So no open-three completion.
    CHECK_FALSE(line_has_naive_open_three(line));
}

TEST_CASE("line_has_naive_open_three: not a three (just two)") {
    Line line = make_line({0, 0, 0, 0, 1, 1, 0, 0, 0});
    CHECK_FALSE(line_has_naive_open_three(line));
}
