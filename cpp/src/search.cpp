#include "omok/search.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstring>
#include <utility>

#include "omok/movegen.hpp"

namespace omok::search {

namespace {

constexpr int INF = 2'000'000;

// Pop-count round up to power of two (>= 1).
std::size_t round_up_pow2(std::size_t n) {
    std::size_t p = 1;
    while (p < n) p <<= 1;
    return p;
}

int color_index(Color c) { return c == Color::Black ? 0 : 1; }

// Adjust a mate score for distance-to-root: deeper mates are worse than nearer
// mates, so the TT can compare them sensibly across plies.
int score_to_tt(int score, int ply) {
    if (score >  eval::WIN_THRESHOLD) return score + ply;
    if (score < -eval::WIN_THRESHOLD) return score - ply;
    return score;
}
int score_from_tt(int score, int ply) {
    if (score >  eval::WIN_THRESHOLD) return score - ply;
    if (score < -eval::WIN_THRESHOLD) return score + ply;
    return score;
}

}  // namespace

Searcher::Searcher(std::size_t tt_size_mb) {
    std::size_t entries = (tt_size_mb * 1024 * 1024) / sizeof(TTEntry);
    if (entries < 1024) entries = 1024;
    entries = round_up_pow2(entries);
    tt_.assign(entries, TTEntry{});
    tt_mask_ = entries - 1;
    clear();
}

void Searcher::clear() {
    std::fill(tt_.begin(), tt_.end(), TTEntry{});
    for (int p = 0; p < MAX_PLY; ++p) {
        killers_[p][0] = Move{-1, -1};
        killers_[p][1] = Move{-1, -1};
    }
    std::memset(history_, 0, sizeof(history_));
    nodes_ = 0;
    tt_hits_ = 0;
}

bool Searcher::time_up() const {
    if (aborted_) return true;
    return std::chrono::steady_clock::now() >= deadline_;
}

void Searcher::store_tt(std::uint64_t key, int depth, int score, TTFlag flag, Move best) {
    TTEntry& slot = tt_[key & tt_mask_];
    // Always-replace policy. Could refine later (depth-preferred + always-replace bucket).
    slot.key   = key;
    slot.depth = static_cast<std::int8_t>(std::clamp(depth, -1, 127));
    slot.score = static_cast<std::int32_t>(score);
    slot.flag  = flag;
    slot.best  = best;
}

const TTEntry* Searcher::probe_tt(std::uint64_t key) const {
    const TTEntry& slot = tt_[key & tt_mask_];
    if (slot.key == key) return &slot;
    return nullptr;
}

void Searcher::remember_killer(int ply, Move m) {
    if (ply < 0 || ply >= MAX_PLY) return;
    if (killers_[ply][0] == m) return;
    killers_[ply][1] = killers_[ply][0];
    killers_[ply][0] = m;
}

bool Searcher::is_killer(int ply, Move m) const {
    if (ply < 0 || ply >= MAX_PLY) return false;
    return killers_[ply][0] == m || killers_[ply][1] == m;
}

int Searcher::negamax(Board& b, Color to_move, int depth, int ply, int alpha, int beta) {
    ++nodes_;

    // Periodic time check.
    if ((nodes_ & 0x3FF) == 0 && time_up()) {
        aborted_ = true;
        return 0;
    }

    // Terminal check: did the opponent's previous move just win?
    if (rules_->last_move_wins(b)) {
        // Side that just moved won; from current to_move's perspective that's a loss.
        return -eval::WIN + ply;
    }

    if (depth <= 0) {
        return eval::evaluate(b, to_move, weights_);
    }

    std::uint64_t key = b.hash();
    Move tt_best{-1, -1};
    if (const TTEntry* hit = probe_tt(key)) {
        ++tt_hits_;
        if (hit->depth >= depth) {
            int s = score_from_tt(hit->score, ply);
            if (hit->flag == TTFlag::Exact) return s;
            if (hit->flag == TTFlag::LowerBound && s >= beta)  return s;
            if (hit->flag == TTFlag::UpperBound && s <= alpha) return s;
        }
        tt_best = hit->best;
    }

    int width = (ply == 0) ? limits_.root_width : limits_.child_width;
    auto moves = movegen::generate(b, to_move, *rules_, width, /*radius=*/2, weights_);
    if (moves.empty()) {
        // No legal moves (e.g., all neighbours forbidden for black) — treat as static eval.
        return eval::evaluate(b, to_move, weights_);
    }

    // Move ordering: TT best first, then killers, then history bonus on top of candidate score.
    auto order_key = [&](const movegen::ScoredMove& sm) -> long long {
        long long k = static_cast<long long>(sm.score);
        if (sm.move == tt_best)                                                       k += 1'000'000'000LL;
        else if (is_killer(ply, sm.move))                                             k += 500'000'000LL;
        k += static_cast<long long>(history_[color_index(to_move)][sm.move.index()]);
        return k;
    };
    std::sort(moves.begin(), moves.end(),
              [&](const movegen::ScoredMove& a, const movegen::ScoredMove& bb) {
                  return order_key(a) > order_key(bb);
              });

    int best_score = -INF;
    Move best_move = moves.front().move;
    int original_alpha = alpha;

    for (const auto& sm : moves) {
        if (!b.play(sm.move, to_move)) continue;
        int sc = -negamax(b, opponent(to_move), depth - 1, ply + 1, -beta, -alpha);
        b.undo();

        if (aborted_) return 0;

        if (sc > best_score) {
            best_score = sc;
            best_move  = sm.move;
        }
        if (sc > alpha) alpha = sc;
        if (alpha >= beta) {
            // Beta cut: this move refuted the opponent's hypothesis. Reward it.
            remember_killer(ply, sm.move);
            int& h = history_[color_index(to_move)][sm.move.index()];
            h += depth * depth;
            if (h > 1'000'000) {
                // Periodic decay to keep the table fresh.
                for (int& cell : history_[color_index(to_move)]) cell /= 2;
            }
            break;
        }
    }

    TTFlag flag = TTFlag::Exact;
    if (best_score <= original_alpha)      flag = TTFlag::UpperBound;
    else if (best_score >= beta)           flag = TTFlag::LowerBound;
    store_tt(key, depth, score_to_tt(best_score, ply), flag, best_move);
    return best_score;
}

SearchResult Searcher::search(Board& b, Color to_move, const RuleChecker& rules,
                              const SearchLimits& limits, const eval::Weights& w) {
    rules_   = &rules;
    weights_ = w;
    limits_  = limits;
    aborted_ = false;
    nodes_   = 0;
    tt_hits_ = 0;

    auto start = std::chrono::steady_clock::now();
    deadline_  = start + std::chrono::milliseconds(std::max(1, limits.budget_ms));

    SearchResult result;

    // Generate root moves once; we'll re-sort per iteration using TT best from prior depth.
    auto root_moves = movegen::generate(b, to_move, rules,
                                        /*max_keep=*/limits.root_width, /*radius=*/2, w);
    if (root_moves.empty()) {
        result.best_move = Move{BOARD_SIZE / 2, BOARD_SIZE / 2};
        return result;
    }
    result.best_move = root_moves.front().move;
    result.score     = root_moves.front().score;

    Move overall_best = result.best_move;

    for (int depth = 1; depth <= limits.max_depth; ++depth) {
        if (time_up()) break;

        // Re-order using current TT best.
        std::uint64_t root_key = b.hash();
        Move tt_best{-1, -1};
        if (const TTEntry* hit = probe_tt(root_key)) tt_best = hit->best;

        std::sort(root_moves.begin(), root_moves.end(),
                  [&](const movegen::ScoredMove& a, const movegen::ScoredMove& bb) {
                      long long ka = a.score + (a.move == tt_best ? 1'000'000'000LL : 0);
                      long long kb = bb.score + (bb.move == tt_best ? 1'000'000'000LL : 0);
                      return ka > kb;
                  });

        int alpha = -INF, beta = INF;
        int best_score = -INF;
        Move best_move = root_moves.front().move;

        for (const auto& sm : root_moves) {
            if (!b.play(sm.move, to_move)) continue;
            int sc = -negamax(b, opponent(to_move), depth - 1, /*ply=*/1, -beta, -alpha);
            b.undo();

            if (aborted_) break;

            if (sc > best_score) {
                best_score = sc;
                best_move  = sm.move;
            }
            if (sc > alpha) alpha = sc;
        }

        if (aborted_) {
            result.aborted = true;
            break;
        }

        // Commit results from this completed depth.
        result.score     = best_score;
        result.best_move = best_move;
        result.depth     = depth;
        overall_best     = best_move;

        // Store root in TT so the next depth's ordering picks it up.
        store_tt(root_key, depth, score_to_tt(best_score, 0), TTFlag::Exact, best_move);

        // Proven mate found: no point searching deeper.
        if (best_score >= eval::WIN_THRESHOLD || best_score <= -eval::WIN_THRESHOLD) {
            break;
        }
    }

    result.best_move = overall_best;
    auto end = std::chrono::steady_clock::now();
    result.elapsed_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count());
    result.nodes      = nodes_;
    result.tt_hits    = tt_hits_;
    return result;
}

}  // namespace omok::search
