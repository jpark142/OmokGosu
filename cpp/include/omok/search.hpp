#pragma once

#include <chrono>
#include <cstdint>
#include <vector>

#include "omok/board.hpp"
#include "omok/eval.hpp"
#include "omok/rules.hpp"
#include "omok/types.hpp"

namespace omok::search {

struct SearchLimits {
    int max_depth   = 8;       // hard cap on iterative deepening depth
    int budget_ms   = 1000;    // wallclock deadline; ID stops when exceeded
    int root_width  = 16;      // top-K moves considered at the root
    int child_width = 10;      // top-K moves considered at non-root nodes
};

struct SearchResult {
    Move      best_move{0, 0};
    int       score        = 0;       // from to_move's perspective
    int       depth        = 0;       // last fully-completed depth
    std::uint64_t nodes    = 0;
    std::uint64_t tt_hits  = 0;
    int       elapsed_ms   = 0;
    bool      aborted      = false;   // true if we returned early due to time budget
};

// One transposition-table entry. 16 bytes when packed; we keep it slightly
// larger for clarity since memory isn't the bottleneck here.
enum class TTFlag : std::uint8_t { Exact = 0, LowerBound = 1, UpperBound = 2 };

struct TTEntry {
    std::uint64_t key   = 0;
    std::int32_t  score = 0;
    Move          best  = Move{-1, -1};
    std::int8_t   depth = -1;
    TTFlag        flag  = TTFlag::Exact;
};

// Negamax searcher with alpha-beta, transposition table, iterative deepening,
// killer/history move ordering, and a wall-clock deadline.
//
// Stateful so the TT and history tables persist across `search()` calls within
// the same game (the caller may also call `clear()` between games).
class Searcher {
public:
    explicit Searcher(std::size_t tt_size_mb = 32);

    // Reset TT and history tables. Call between games.
    void clear();

    // Top-level entry. `b` is mutated transiently but restored before return.
    SearchResult search(Board& b, Color to_move, const RuleChecker& rules,
                        const SearchLimits& limits,
                        const eval::Weights& w = eval::Weights{});

private:
    int negamax(Board& b, Color to_move, int depth, int ply, int alpha, int beta);

    bool       time_up() const;
    void       store_tt(std::uint64_t key, int depth, int score, TTFlag flag, Move best);
    const TTEntry* probe_tt(std::uint64_t key) const;

    void  remember_killer(int ply, Move m);
    bool  is_killer(int ply, Move m) const;

    // --- state shared across one search() call ---
    const RuleChecker* rules_ = nullptr;
    eval::Weights      weights_{};
    SearchLimits       limits_{};
    std::chrono::steady_clock::time_point deadline_{};
    bool aborted_ = false;
    std::uint64_t nodes_ = 0;
    std::uint64_t tt_hits_ = 0;

    // --- persistent across calls ---
    std::vector<TTEntry> tt_;
    std::size_t          tt_mask_ = 0;
    // killer_[ply][slot]: 2 killer moves per ply
    static constexpr int MAX_PLY = 64;
    Move killers_[MAX_PLY][2];
    // history_[color_index][square]: heuristic ordering bonus for moves that caused beta cuts
    int history_[2][CELL_COUNT];
};

}  // namespace omok::search
