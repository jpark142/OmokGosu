#include "omok/vcf.hpp"

#include <algorithm>
#include <array>
#include <bitset>
#include <functional>

#include "omok/pattern.hpp"
#include "omok/rules.hpp"

namespace omok::vcf {

namespace {

using pattern::Line;

// Empty cells within Chebyshev radius 2 of any stone on the board.
// On an empty board returns just the center.
std::vector<Move> candidate_moves(const Board& b) {
    std::vector<Move> out;
    if (b.move_count() == 0) {
        out.push_back(Move{BOARD_SIZE / 2, BOARD_SIZE / 2});
        return out;
    }
    std::bitset<CELL_COUNT> seen;
    out.reserve(40);
    for (const auto& e : b.history()) {
        for (int dr = -2; dr <= 2; ++dr) {
            for (int dc = -2; dc <= 2; ++dc) {
                int r = e.move.r + dr;
                int c = e.move.c + dc;
                if (r < 0 || r >= BOARD_SIZE || c < 0 || c >= BOARD_SIZE) continue;
                int idx = r * BOARD_SIZE + c;
                if (seen.test(idx)) continue;
                if (b.at(r, c) != Color::Empty) continue;
                seen.set(idx);
                out.push_back(Move{static_cast<std::int8_t>(r),
                                   static_cast<std::int8_t>(c)});
            }
        }
    }
    return out;
}

// All empty squares that, when filled with `color`, complete a five through
// `four_move` (which must already be occupied by `color`). For BLACK, only
// exact-five completions count — overline completions are forbidden so they
// don't constitute a real five-threat.
std::vector<Move> five_completion_squares(const Board& b, Color color, Move four_move) {
    std::vector<Move> out;
    const bool require_exact_five = (color == Color::Black);

    for (Dir d : DIRECTIONS) {
        Line line = pattern::extract_line(b, four_move, color, d);
        if (line.v[Line::CENTER] != 1) continue;  // safety
        for (int i = 0; i < Line::LEN; ++i) {
            if (i == Line::CENTER) continue;
            if (line.v[i] != 0) continue;
            Line t = line;
            t.v[i] = 1;
            int run = pattern::run_length_through_center(t);
            bool ok = require_exact_five ? (run == 5) : (run >= 5);
            if (!ok) continue;
            int offset = i - Line::CENTER;
            Move c{static_cast<std::int8_t>(four_move.r + d.dr * offset),
                   static_cast<std::int8_t>(four_move.c + d.dc * offset)};
            if (!c.in_bounds()) continue;
            if (b.at(c) != Color::Empty) continue;
            bool dup = false;
            for (auto& r : out) { if (r == c) { dup = true; break; } }
            if (!dup) out.push_back(c);
        }
    }
    return out;
}

// True iff `color` (already placed at `move`) has at least one square that
// completes a five through that move. The board is queried as-is.
bool creates_four(const Board& b, Move move, Color color) {
    return !five_completion_squares(b, color, move).empty();
}

}  // namespace

VcfResult find_vcf(Board& board, Color color, int max_depth) {
    VcfResult result;
    if (color != Color::Black && color != Color::White) return result;
    if (max_depth <= 0) return result;

    const RuleChecker rules;
    const Color opp = opponent(color);

    // Recursive helper: returns true iff `color` (to move on `board`) has a
    // VCF win within `remaining` plies. On true, appends the winning sequence
    // to `seq` in order (own, opp, own, opp, ..., own).
    std::function<bool(int, std::vector<Move>&)> solve;
    solve = [&](int remaining, std::vector<Move>& seq) -> bool {
        if (remaining <= 0) return false;
        ++result.nodes;

        const auto cands = candidate_moves(board);

        // Step 1 — own immediate winning move.
        for (Move m : cands) {
            if (color == Color::Black &&
                rules.classify_for_black(board, m) != ForbiddenKind::None) continue;
            if (rules.is_winning_move(board, m, color)) {
                seq.push_back(m);
                return true;
            }
        }

        // Step 2 — moves that create at least one four (forcing opp to block).
        // We try the strongest moves first (more completion squares = open four = instant).
        struct Cand { Move m; std::vector<Move> completions; };
        std::vector<Cand> threats;
        threats.reserve(8);

        for (Move m : cands) {
            if (color == Color::Black &&
                rules.classify_for_black(board, m) != ForbiddenKind::None) continue;
            if (!board.play(m, color)) continue;
            auto comps = five_completion_squares(board, color, m);
            board.undo();
            if (!comps.empty()) threats.push_back({m, std::move(comps)});
        }

        // Open fours (≥2 completion squares from a single move) win in 2 plies:
        // opp blocks one, we play the other.
        std::sort(threats.begin(), threats.end(),
                  [](const Cand& a, const Cand& b) {
                      return a.completions.size() > b.completions.size();
                  });

        for (const auto& th : threats) {
            board.play(th.m, color);

            // Multi-completion (open-four-ish): opp must block one; we play the other.
            if (th.completions.size() >= 2) {
                // Opp picks the first completion; we look for a remaining one that's
                // still a winning move after the block.
                Move opp_block = th.completions[0];
                board.play(opp_block, opp);
                Move winning_continuation{0, 0};
                bool found = false;
                for (size_t i = 1; i < th.completions.size(); ++i) {
                    Move cand = th.completions[i];
                    if (board.at(cand) != Color::Empty) continue;
                    if (color == Color::Black &&
                        rules.classify_for_black(board, cand) != ForbiddenKind::None) continue;
                    if (rules.is_winning_move(board, cand, color)) {
                        winning_continuation = cand;
                        found = true;
                        break;
                    }
                }
                board.undo();  // undo opp's block
                if (found) {
                    board.undo();  // undo own four
                    seq.push_back(th.m);
                    seq.push_back(opp_block);
                    seq.push_back(winning_continuation);
                    return true;
                }
                // else fall through to recurse using just the first completion as the block
            }

            // Closed four (or open-four where the simple double-tap didn't work):
            // opp must play the single forced block (we use completions[0]).
            Move blk = th.completions[0];
            board.play(blk, opp);
            std::vector<Move> sub;
            // Depth budget decrement: own move + opp block = one ply each, but we
            // count only OWN plies so subtract 1.
            bool sub_win = solve(remaining - 1, sub);
            board.undo();  // opp's block
            board.undo();  // own four

            if (sub_win) {
                seq.push_back(th.m);
                seq.push_back(blk);
                for (auto& sm : sub) seq.push_back(sm);
                return true;
            }
        }

        return false;
    };

    result.found = solve(max_depth, result.sequence);
    return result;
}

}  // namespace omok::vcf
