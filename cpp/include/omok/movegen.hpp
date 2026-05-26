#pragma once

#include <vector>

#include "omok/board.hpp"
#include "omok/eval.hpp"
#include "omok/rules.hpp"
#include "omok/types.hpp"

namespace omok::movegen {

struct ScoredMove {
    Move move;
    int score;  // higher = better candidate (used for ordering, NOT eval)
};

// Generate candidate moves for `to_move`, sorted descending by candidate score.
// Candidate set: empty cells within Chebyshev distance `radius` of any stone.
// First move on empty board returns just the center.
//
// For BLACK, forbidden squares (3-3 / 4-4 / overline) are filtered out via
// `rules`. `rules` is non-const because classify_for_black mutates the board
// transiently (it always restores).
//
// `max_keep`: if positive, truncate the result to top-N. Use 0 for unlimited.
std::vector<ScoredMove> generate(Board& b, Color to_move, const RuleChecker& rules,
                                 int max_keep = 0, int radius = 2,
                                 const eval::Weights& w = eval::Weights{});

// Quick per-candidate score: how much threat does playing this move create?
// Sums own-pattern-gain + opponent-pattern-block. Cheap, used for ordering.
int candidate_score(Board& b, Move m, Color to_move,
                    const eval::Weights& w = eval::Weights{});

}  // namespace omok::movegen
