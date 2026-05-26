#include <doctest/doctest.h>

#include <chrono>

#include "omok/board.hpp"
#include "omok/eval.hpp"
#include "omok/rules.hpp"
#include "omok/search.hpp"

using namespace omok;

namespace {

struct Stone { int r, c; Color color; };
void place_all(Board& b, std::initializer_list<Stone> stones) {
    for (const auto& s : stones) {
        REQUIRE(b.play(Move{static_cast<std::int8_t>(s.r), static_cast<std::int8_t>(s.c)}, s.color));
    }
}

}  // namespace

TEST_CASE("evaluate: empty board is symmetric (score == 0)") {
    Board b;
    CHECK(eval::evaluate(b, Color::Black) == 0);
    CHECK(eval::evaluate(b, Color::White) == 0);
}

TEST_CASE("evaluate: side with an open three is meaningfully positive") {
    Board b;
    // Black has _BBB_ horizontally; white has nothing nearby.
    place_all(b, {
        {7, 5, Color::Black}, {0, 0, Color::White},
        {7, 6, Color::Black}, {0, 1, Color::White},
        {7, 7, Color::Black},
    });
    int s_black = eval::evaluate(b, Color::Black);
    int s_white = eval::evaluate(b, Color::White);
    CHECK(s_black > 0);
    CHECK(s_white < 0);
    CHECK(s_black == -s_white);
}

TEST_CASE("search: white finds mate-in-1 (place at 7,7 makes five)") {
    Board b;
    // White has 4 in a row with both ends open at 7,2..7,5; can play 7,6 or 7,1 to win.
    // Construct so it's white-to-move.
    place_all(b, {
        {0, 0, Color::Black},
        {7, 2, Color::White}, {1, 0, Color::Black},
        {7, 3, Color::White}, {2, 0, Color::Black},
        {7, 4, Color::White}, {3, 0, Color::Black},
        {7, 5, Color::White}, {4, 0, Color::Black},
    });
    REQUIRE(b.side_to_move() == Color::White);

    search::Searcher s;
    search::SearchLimits lim;
    lim.max_depth = 2;
    lim.budget_ms = 500;
    auto r = s.search(b, Color::White, RuleChecker{}, lim);
    // Best should win; the move should extend the row to 5.
    CHECK(r.score >= eval::WIN_THRESHOLD);
    bool ok = (r.best_move.r == 7 && (r.best_move.c == 1 || r.best_move.c == 6));
    CHECK(ok);
}

TEST_CASE("search: black must block opponent's closed-four mate") {
    Board b;
    // White has 4 in a row at 7,0..7,3 — one side blocked by the left wall.
    // Black is to move; the only blocking square is (7,4). Anything else loses
    // to white playing (7,4) for the 5-in-a-row.
    // Dummy black stones placed far apart so they don't form a counter-threat.
    place_all(b, {
        {0, 14, Color::Black},
        {7, 0, Color::White}, {2, 14, Color::Black},
        {7, 1, Color::White}, {4, 14, Color::Black},
        {7, 2, Color::White}, {0, 12, Color::Black},
        {7, 3, Color::White},
    });
    REQUIRE(b.side_to_move() == Color::Black);

    search::Searcher s;
    search::SearchLimits lim;
    lim.max_depth = 3;
    lim.budget_ms = 800;
    auto r = s.search(b, Color::Black, RuleChecker{}, lim);
    INFO("best_move = (", int(r.best_move.r), ",", int(r.best_move.c), ") score=", r.score,
         " depth=", r.depth, " nodes=", r.nodes);
    bool blocked = (r.best_move.r == 7 && r.best_move.c == 4);
    CHECK(blocked);
}

TEST_CASE("search: respects time budget (returns without hanging)") {
    Board b;
    place_all(b, {{7, 7, Color::Black}, {7, 8, Color::White}});  // a few stones to seed candidates

    search::Searcher s;
    search::SearchLimits lim;
    lim.max_depth = 20;
    lim.budget_ms = 200;
    auto start = std::chrono::steady_clock::now();
    auto r = s.search(b, b.side_to_move(), RuleChecker{}, lim);
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - start).count();

    // Should finish within ~budget + a generous slack.
    CHECK(elapsed < 2000);
    CHECK(r.depth >= 1);
    CHECK(r.best_move.in_bounds());
}

TEST_CASE("search: empty board picks the center") {
    Board b;
    search::Searcher s;
    search::SearchLimits lim;
    lim.max_depth = 2;
    lim.budget_ms = 200;
    auto r = s.search(b, Color::Black, RuleChecker{}, lim);
    CHECK(r.best_move.r == BOARD_SIZE / 2);
    CHECK(r.best_move.c == BOARD_SIZE / 2);
}
