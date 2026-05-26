#include <doctest/doctest.h>

#include "omok/board.hpp"

using namespace omok;

TEST_CASE("Board starts empty with black to move") {
    Board b;
    CHECK(b.move_count() == 0);
    CHECK(b.side_to_move() == Color::Black);
    CHECK(b.hash() == 0ULL);
    for (int i = 0; i < BOARD_SIZE * BOARD_SIZE; ++i) {
        Move m = Move::from_index(i);
        CHECK(b.at(m) == Color::Empty);
    }
}

TEST_CASE("Board play and undo invariants") {
    Board b;
    std::uint64_t initial_hash = b.hash();

    CHECK(b.play(Move{7, 7}, Color::Black));
    CHECK(b.at(7, 7) == Color::Black);
    CHECK(b.side_to_move() == Color::White);
    CHECK(b.move_count() == 1);
    CHECK(b.hash() != initial_hash);

    CHECK(b.play(Move{7, 8}, Color::White));
    CHECK(b.at(7, 8) == Color::White);
    CHECK(b.side_to_move() == Color::Black);
    CHECK(b.move_count() == 2);

    std::uint64_t two_move_hash = b.hash();

    b.undo();
    CHECK(b.at(7, 8) == Color::Empty);
    CHECK(b.side_to_move() == Color::White);
    CHECK(b.move_count() == 1);

    b.undo();
    CHECK(b.at(7, 7) == Color::Empty);
    CHECK(b.side_to_move() == Color::Black);
    CHECK(b.move_count() == 0);
    CHECK(b.hash() == initial_hash);

    // Re-play same moves yields same hash (zobrist invariant).
    b.play(Move{7, 7}, Color::Black);
    b.play(Move{7, 8}, Color::White);
    CHECK(b.hash() == two_move_hash);
}

TEST_CASE("Board rejects illegal plays") {
    Board b;
    CHECK_FALSE(b.play(Move{-1, 0}, Color::Black));
    CHECK_FALSE(b.play(Move{0, BOARD_SIZE}, Color::Black));
    CHECK_FALSE(b.play(Move{0, 0}, Color::Empty));

    REQUIRE(b.play(Move{5, 5}, Color::Black));
    CHECK_FALSE(b.play(Move{5, 5}, Color::White));  // occupied
}

TEST_CASE("Board undo on empty history is a no-op") {
    Board b;
    b.undo();
    CHECK(b.move_count() == 0);
    CHECK(b.side_to_move() == Color::Black);
}
