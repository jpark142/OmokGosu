#pragma once

#include "omok/board.hpp"
#include "omok/types.hpp"

namespace omok::eval {

// Score magnitudes. WIN is a hard terminal that dominates everything else; the
// search treats |score| >= WIN_THRESHOLD as a proven mate.
constexpr int WIN          = 1'000'000;
constexpr int WIN_THRESHOLD = 900'000;

// Pattern weights (one side, "my" perspective). Negative weights mean "bad for
// me" — but the eval composes them as my_score - opp_score, so we only need
// positive weights here.
struct Weights {
    int five           = WIN;        // 5-in-a-row (white) / exact-5 (black)
    int open_four      = 50'000;     // _XXXX_ — opponent must respond, two ways to make 5
    int four           = 10'000;     // closed/simple four — one way to make 5
    int open_three     = 5'000;      // _XXX_ surrounded by enough space to extend to open-4
    int closed_three   = 500;
    int open_two       = 100;
    int closed_two     = 10;
    int overline_black = -100'000;   // 6+-in-a-row when "my" is black: forbidden, treated as bad
};

// Static evaluation from the perspective of `to_move`:
//   score = score_for(to_move) - score_for(opponent)
// Positive means to_move is winning. Result clipped to [-WIN, +WIN].
//
// If to_move is BLACK, black overlines contribute the negative weight (they're
// terminal forbidden) rather than five. If WHITE, overlines count as five.
int evaluate(const Board& b, Color to_move, const Weights& w = Weights{});

// Single-color score (sum of all pattern values for color `c`). Used by movegen
// for candidate ordering — cheaper than running full evaluate twice.
int score_for(const Board& b, Color c, const Weights& w = Weights{});

}  // namespace omok::eval
