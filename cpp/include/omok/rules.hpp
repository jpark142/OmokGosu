#pragma once

#include <vector>

#include "omok/board.hpp"
#include "omok/types.hpp"

namespace omok {

class RuleChecker {
public:
    static constexpr int MAX_RECURSION_DEPTH = 8;

    // True if placing `c` at `m` would win the game per Renju rules.
    //   - For BLACK: only an exact 5-in-a-row wins (overline forbidden, not a win).
    //   - For WHITE: 5-in-a-row or more wins.
    // Requires: m in bounds and currently empty.
    bool is_winning_move(const Board& b, Move m, Color c) const;

    // Return the forbidden classification if BLACK plays at m. Returns None if the move
    // is legal for black (including when it is a winning move — those are not forbidden).
    // Requires: m in bounds and currently empty.
    //
    // Modifies `b` transiently (plays/undos m and intermediate stones during recursive
    // open-three validation), but on return b is identical to the input.
    ForbiddenKind classify_for_black(Board& b, Move m, int depth = 0) const;

    // True iff the last move on the board is a winning move for its color.
    // Used after move application (to detect game end). Scans 4 directions from the last move.
    bool last_move_wins(const Board& b) const;

    // Compute the set of forbidden squares for the given color (only meaningful when color is BLACK).
    // Returns empty vector for WHITE. Used by the server to push `forbidden_squares` to the UI.
    std::vector<Move> compute_forbidden_squares(Board& b, Color c) const;
};

}  // namespace omok
