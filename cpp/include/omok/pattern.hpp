#pragma once

#include <array>

#include "omok/board.hpp"
#include "omok/types.hpp"

namespace omok::pattern {

// 9-cell 1-D line centered at a candidate move.
// Encoding: 0=empty, 1=mine, 2=opponent, 3=wall (off-board).
struct Line {
    static constexpr int LEN = 9;
    static constexpr int CENTER = 4;
    std::array<int, LEN> v{};
};

// Extract the 9-cell line centered at `m` along direction `d`, encoded relative to `my`.
// The center cell (v[4]) reflects whatever is currently on the board at m
// (typically Empty; caller can overwrite to 1 to simulate placing `my` there).
Line extract_line(const Board& b, Move m, Color my, Dir d);

// Length of the maximal contiguous run of mine-stones through the center.
// Returns 0 if the center is not mine.
int run_length_through_center(const Line& line);

// True if the line has a 5-in-a-row containing the center (>=5 for white; check exact-5 separately for black win).
bool makes_five_or_more_through_center(const Line& line);

// True iff the line has *exactly* a 5-in-a-row containing the center.
bool makes_exact_five_through_center(const Line& line);

// True iff the line has a 6+-in-a-row containing the center.
bool makes_overline_through_center(const Line& line);

// True if any empty cell in the line, when virtually filled with mine, results in
// a 5-in-a-row through center. (i.e., the line currently contains a "four" through center.)
// Out-parameter: list of completion offsets (window indices 0..8) if requested.
bool line_has_four(const Line& line, std::array<int, 9>* completions = nullptr,
                   int* num_completions = nullptr);

// True if any empty cell in the line, when virtually filled with mine, results in
// an *open four* (4-run with both ends empty) through center. (i.e., line currently
// contains a naive open three.) Out-parameter: completion window indices.
//
// "Naive" because the recursive validation — whether the open-four-completing move
// is itself legal for black — is performed in RuleChecker, not here.
bool line_has_naive_open_three(const Line& line, std::array<int, 9>* completions = nullptr,
                               int* num_completions = nullptr);

}  // namespace omok::pattern
