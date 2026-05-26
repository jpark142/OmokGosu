#include <doctest/doctest.h>

#include "omok/board.hpp"
#include "omok/rules.hpp"

using namespace omok;

namespace {

// Convenience: scatter a list of stones on a board.
struct Stone { int r, c; Color color; };
void place_all(Board& b, std::initializer_list<Stone> stones) {
    for (const auto& s : stones) {
        REQUIRE(b.play(Move{static_cast<std::int8_t>(s.r), static_cast<std::int8_t>(s.c)}, s.color));
    }
}

}  // namespace

TEST_CASE("is_winning_move: black wins on exact five horizontal") {
    Board b;
    place_all(b, {
        {7, 3, Color::Black}, {7, 4, Color::Black},
        {7, 5, Color::Black}, {7, 6, Color::Black},
        {0, 0, Color::White},  // dummy white to balance turn
    });
    RuleChecker rc;
    CHECK(rc.is_winning_move(b, Move{7, 7}, Color::Black));
}

TEST_CASE("is_winning_move: black playing into 6-stones-row does NOT win (overline)") {
    Board b;
    // Black at 7,2..7,5 already (4 stones). Then black 7,7..7,8 (2 more). Playing 7,6 connects all six.
    place_all(b, {
        {7, 2, Color::Black}, {7, 3, Color::Black},
        {7, 4, Color::Black}, {7, 5, Color::Black},
        {0, 0, Color::White},
        {7, 7, Color::Black}, {0, 1, Color::White},
        {7, 8, Color::Black}, {0, 2, Color::White},
    });
    RuleChecker rc;
    CHECK_FALSE(rc.is_winning_move(b, Move{7, 6}, Color::Black));
}

TEST_CASE("is_winning_move: white wins on six-in-a-row (overline allowed)") {
    Board b;
    place_all(b, {
        {0, 0, Color::Black},
        {7, 2, Color::White}, {1, 0, Color::Black},
        {7, 3, Color::White}, {2, 0, Color::Black},
        {7, 4, Color::White}, {3, 0, Color::Black},
        {7, 5, Color::White}, {4, 0, Color::Black},
        {7, 7, Color::White}, {5, 0, Color::Black},
        {7, 8, Color::White}, {6, 0, Color::Black},
    });
    RuleChecker rc;
    CHECK(rc.is_winning_move(b, Move{7, 6}, Color::White));
}

TEST_CASE("classify_for_black: ordinary move is legal") {
    Board b;
    RuleChecker rc;
    CHECK(rc.classify_for_black(b, Move{7, 7}) == ForbiddenKind::None);
}

TEST_CASE("classify_for_black: overline is forbidden") {
    Board b;
    place_all(b, {
        {7, 2, Color::Black}, {0, 0, Color::White},
        {7, 3, Color::Black}, {0, 1, Color::White},
        {7, 4, Color::Black}, {0, 2, Color::White},
        {7, 5, Color::Black}, {0, 3, Color::White},
        {7, 7, Color::Black}, {0, 4, Color::White},
        {7, 8, Color::Black}, {0, 5, Color::White},
    });
    RuleChecker rc;
    // Placing at 7,6 connects 7,2..7,8 = 7 black stones in a row → overline.
    CHECK(rc.classify_for_black(b, Move{7, 6}) == ForbiddenKind::Overline);
}

TEST_CASE("classify_for_black: double-three at intersection") {
    Board b;
    // Build two open threes that intersect at one square.
    // Horizontal: _BB_BB_ pattern around (7,7) ... place black 7,5 7,6 7,8 7,9 (line of _BB?BB_ centered at 7,7)
    // Actually placing at 7,7 would make _BBBBB_ (5-in-row) — that's a win not a forbidden. Let me redesign.
    //
    // Classic double-three: black at (7,5), (7,6); and at (5,7), (6,7). Now place at (7,7).
    //   Row 7 has black at cols 5,6, then candidate 7, → run of 3 horizontally with open both sides → open three.
    //   Col 7 has black at rows 5,6, then candidate 7, → run of 3 vertically with open both sides → open three.
    // Two open threes through (7,7) → 3-3.
    place_all(b, {
        {7, 5, Color::Black}, {0, 0, Color::White},
        {7, 6, Color::Black}, {0, 1, Color::White},
        {5, 7, Color::Black}, {0, 2, Color::White},
        {6, 7, Color::Black}, {0, 3, Color::White},
    });
    RuleChecker rc;
    CHECK(rc.classify_for_black(b, Move{7, 7}) == ForbiddenKind::DoubleThree);
}

TEST_CASE("classify_for_black: double-four at intersection") {
    Board b;
    // Build two fours sharing one square. Horizontal: black at 7,4 7,5 7,7 7,8 — placing at 7,6 makes 5.
    //   Wait that's a single direction four, not two.
    //
    // Vertical four AND horizontal four: at (7,7),
    //   horizontal: black at (7,3) (7,4) (7,5) (7,6) — placing at 7,7 makes 5 horizontally (a five, not a four!).
    // So we need to set up fours that are NOT fives.
    //
    // Classic: black at (7,3) (7,4) (7,5) — horizontal three. Placing at (7,7) plus existing means... no.
    //
    // Better example: two "broken fours". Place black at (7,3) (7,4) (7,6) (7,7) — horizontal "BB_BB" through 7,5.
    //   Placing at 7,5 → 5-in-row. So is_winning, not forbidden.
    //
    // Real double-four scenario without creating a five: black at (7,4) (7,5) and at (5,7) (6,7) and at (8,7) (9,7).
    //   Vertical column 7 has black at 5,6,8,9 — placing at 7,7 connects 5..9 (5 stones) → win, not forbidden.
    //
    // Use closed fours: black at (7,2)(7,3)(7,4)(7,5) [horizontal block of 4, candidate at 7,6 makes 5 → win].
    //
    // True double-four needs candidate that creates two SEPARATE four-shapes (not five).
    // Try: black at (7,3)(7,4)(7,5) and at (5,7)(6,7) [black]; opponent at 7,7's continuation directions to prevent open three classification.
    //
    // Simplest example I know: black has 4-in-a-row with a gap that candidate fills creating two fours in different directions.
    //
    // (5,5)(5,6)(5,7)(5,8) horizontal four — already 4 in row. Candidate at (5,9) makes 5 horizontally. Skip.
    //
    // Use the standard test: place opponent stones to block fives.
    // Black:    (3,7)(4,7)(5,7)  vertical three
    //           (7,3)(7,4)(7,5)  horizontal three
    // Plus blocking white at (2,7) and (7,2) so the "fours" that would form via candidate at (6,7) and (7,6) aren't fives.
    //
    // Let me use a cleaner test: SIMPLE double-four built by closed-four shapes.
    // White at (3,7), Black at (4,7)(5,7)(6,7) → vertical run; placing at (7,7) makes (4..7) = 4 blacks, blocked above by white at 3,7. Closed four.
    // White at (7,3), Black at (7,4)(7,5)(7,6) → horizontal run; placing at (7,7) makes (4..7) = 4 blacks, blocked left by white at 7,3. Closed four.
    // → (7,7) creates two closed fours → 4-4.
    place_all(b, {
        {3, 7, Color::White}, {0, 0, Color::Black},
        {4, 7, Color::Black}, {0, 1, Color::White},
        {5, 7, Color::Black}, {0, 2, Color::White},
        {6, 7, Color::Black}, {0, 3, Color::White},
        {7, 3, Color::White}, {0, 4, Color::Black},
        {7, 4, Color::Black}, {0, 5, Color::White},
        {7, 5, Color::Black}, {0, 6, Color::White},
        {7, 6, Color::Black}, {0, 7, Color::White},
    });
    RuleChecker rc;
    CHECK(rc.classify_for_black(b, Move{7, 7}) == ForbiddenKind::DoubleFour);
}

TEST_CASE("classify_for_black: a five-creating move is NOT forbidden even with overline-elsewhere shape") {
    Board b;
    // Black at (7,4)(7,5)(7,6) horizontal three. Candidate (7,7). Plus existing in (7,8)(7,9) → placing at 7,7 makes 7,4..9 = 6 blacks → overline.
    // BUT, if there is also an exact-five forming via candidate (7,7) in another direction, that wins.
    // Set up: (5,5)(6,6)(8,8)(9,9) black diagonal → (7,7) on diagonal makes 5..9 = 5 blacks (exact 5).
    place_all(b, {
        {7, 4, Color::Black}, {0, 0, Color::White},
        {7, 5, Color::Black}, {0, 1, Color::White},
        {7, 6, Color::Black}, {0, 2, Color::White},
        {7, 8, Color::Black}, {0, 3, Color::White},
        {7, 9, Color::Black}, {0, 4, Color::White},
        {5, 5, Color::Black}, {0, 5, Color::White},
        {6, 6, Color::Black}, {0, 6, Color::White},
        {8, 8, Color::Black}, {0, 7, Color::White},
        {9, 9, Color::Black}, {0, 8, Color::White},
    });
    RuleChecker rc;
    // Horizontal: 7,4..7,9 minus 7,7 — placing at 7,7 makes overline (6 in row).
    // Diagonal: 5,5..9,9 minus 7,7 — placing at 7,7 makes exactly 5 in row.
    // Five wins, overline is not the result.
    CHECK(rc.classify_for_black(b, Move{7, 7}) == ForbiddenKind::None);
    CHECK(rc.is_winning_move(b, Move{7, 7}, Color::Black));
}

TEST_CASE("last_move_wins: black exact five") {
    Board b;
    place_all(b, {
        {7, 3, Color::Black}, {0, 0, Color::White},
        {7, 4, Color::Black}, {0, 1, Color::White},
        {7, 5, Color::Black}, {0, 2, Color::White},
        {7, 6, Color::Black}, {0, 3, Color::White},
        {7, 7, Color::Black},
    });
    RuleChecker rc;
    CHECK(rc.last_move_wins(b));
}

TEST_CASE("last_move_wins: white six in a row (overline counts for white)") {
    Board b;
    place_all(b, {
        {0, 0, Color::Black},
        {7, 3, Color::White}, {1, 0, Color::Black},
        {7, 4, Color::White}, {2, 0, Color::Black},
        {7, 5, Color::White}, {3, 0, Color::Black},
        {7, 6, Color::White}, {4, 0, Color::Black},
        {7, 7, Color::White}, {5, 0, Color::Black},
        {7, 8, Color::White},
    });
    RuleChecker rc;
    CHECK(rc.last_move_wins(b));
}

TEST_CASE("compute_forbidden_squares returns empty for white") {
    Board b;
    RuleChecker rc;
    auto squares = rc.compute_forbidden_squares(b, Color::White);
    CHECK(squares.empty());
}

TEST_CASE("compute_forbidden_squares finds 3-3 squares for black on simple cross setup") {
    Board b;
    place_all(b, {
        {7, 5, Color::Black}, {0, 0, Color::White},
        {7, 6, Color::Black}, {0, 1, Color::White},
        {5, 7, Color::Black}, {0, 2, Color::White},
        {6, 7, Color::Black}, {0, 3, Color::White},
    });
    RuleChecker rc;
    auto squares = rc.compute_forbidden_squares(b, Color::Black);
    bool found = false;
    for (auto& m : squares) {
        if (m.r == 7 && m.c == 7) found = true;
    }
    CHECK(found);
}
