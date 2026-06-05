#pragma once

#include <cstdint>
#include <vector>

#include "omok/board.hpp"
#include "omok/types.hpp"

namespace omok::vcf {

// Result of a VCF (Victory by Continuous Fours) search.
//
// `found=true` means a forced winning sequence exists for the side to move,
// where every own move is a "four" (a 4-in-row that creates a single 5-completion
// threat that the opponent must block).
//
// `sequence` lists the moves in order, alternating own / opp / own / ... ending
// on the final own move that creates the actual 5-in-row. Length is always odd
// (own moves outnumber opp blocks by one).
struct VcfResult {
    bool                    found = false;
    std::vector<Move>       sequence;
    std::uint64_t           nodes = 0;
};

// Search for a VCF win for `color` to move on `board`. `max_depth` counts plies
// (own moves only — opponent's forced responses don't consume depth, since they
// have no choice). Typical useful depth: 12–20.
//
// `board` is mutated transiently during search but restored before return.
VcfResult find_vcf(Board& board, Color color, int max_depth = 16);

}  // namespace omok::vcf
