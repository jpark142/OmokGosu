#include "omok/movegen.hpp"

#include <algorithm>
#include <array>
#include <bitset>

namespace omok::movegen {

namespace {

// Local helper: score the impact of placing `m` as `to_move` and as the opponent,
// summed. We play, score, undo — both ways — so the relative ranking captures
// "this move makes me strong AND denies opponent strength."
int score_after_play(Board& b, Move m, Color c, const eval::Weights& w) {
    if (!b.play(m, c)) return 0;
    int s = eval::score_for(b, c, w);
    b.undo();
    return s;
}

}  // namespace

int candidate_score(Board& b, Move m, Color to_move, const eval::Weights& w) {
    Color opp = opponent(to_move);
    int my_after  = score_after_play(b, m, to_move, w);
    int opp_after = score_after_play(b, m, opp, w);
    // Defense weight slightly under offense so we prefer attacking when threats are equal.
    return my_after + (opp_after * 9) / 10;
}

std::vector<ScoredMove> generate(Board& b, Color to_move, const RuleChecker& rules,
                                 int max_keep, int radius, const eval::Weights& w) {
    std::vector<ScoredMove> out;

    // Empty-board: return the center only.
    if (b.move_count() == 0) {
        out.push_back({Move{BOARD_SIZE / 2, BOARD_SIZE / 2}, 0});
        return out;
    }

    // Build occupancy bitset and mark candidate cells via Chebyshev radius.
    std::bitset<CELL_COUNT> occupied;
    for (const auto& e : b.history()) {
        occupied.set(e.move.index());
    }
    std::bitset<CELL_COUNT> candidate;
    for (int r = 0; r < BOARD_SIZE; ++r) {
        for (int c = 0; c < BOARD_SIZE; ++c) {
            if (!occupied.test(r * BOARD_SIZE + c)) continue;
            for (int dr = -radius; dr <= radius; ++dr) {
                for (int dc = -radius; dc <= radius; ++dc) {
                    int nr = r + dr, nc = c + dc;
                    if (nr < 0 || nr >= BOARD_SIZE || nc < 0 || nc >= BOARD_SIZE) continue;
                    int idx = nr * BOARD_SIZE + nc;
                    if (occupied.test(idx)) continue;
                    candidate.set(idx);
                }
            }
        }
    }

    // For black: pre-filter forbidden squares. classify_for_black mutates `b`
    // transiently; we call it square-by-square.
    std::bitset<CELL_COUNT> forbidden;
    if (to_move == Color::Black) {
        for (int idx = 0; idx < CELL_COUNT; ++idx) {
            if (!candidate.test(idx)) continue;
            Move m = Move::from_index(idx);
            if (rules.classify_for_black(b, m) != ForbiddenKind::None) {
                forbidden.set(idx);
            }
        }
    }

    out.reserve(64);
    for (int idx = 0; idx < CELL_COUNT; ++idx) {
        if (!candidate.test(idx)) continue;
        if (forbidden.test(idx)) continue;
        Move m = Move::from_index(idx);
        int s = candidate_score(b, m, to_move, w);
        out.push_back({m, s});
    }

    std::sort(out.begin(), out.end(),
              [](const ScoredMove& a, const ScoredMove& bb) { return a.score > bb.score; });

    if (max_keep > 0 && static_cast<int>(out.size()) > max_keep) {
        out.resize(max_keep);
    }
    return out;
}

}  // namespace omok::movegen
