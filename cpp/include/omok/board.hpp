#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <vector>

#include "omok/types.hpp"

namespace omok {

// 15x15 board, stored as flat color array + zobrist hash + move stack.
// Bitboards omitted for Phase 1 (correctness first); will introduce in Phase 2 hot paths.
class Board {
public:
    Board();

    void reset();

    Color at(int r, int c) const noexcept;
    Color at(Move m) const noexcept { return at(m.r, m.c); }

    int move_count() const noexcept { return static_cast<int>(history_.size()); }
    Color side_to_move() const noexcept { return side_; }
    std::uint64_t hash() const noexcept { return hash_; }

    // Returns false if the square is occupied or out of bounds.
    // Does NOT check Renju forbidden moves — that is RuleChecker's job.
    bool play(Move m, Color c) noexcept;

    // Undo last play. No-op if history is empty.
    void undo() noexcept;

    // Most recent move, or nullopt.
    std::optional<Move> last_move() const noexcept;

    // Flat snapshot for tests / serialization.
    const std::array<Color, CELL_COUNT>& cells() const noexcept { return cells_; }

    // Convenience: returns true if (r,c) is in bounds AND empty.
    bool is_empty(int r, int c) const noexcept;

    struct HistoryEntry {
        Move move;
        Color color;
        Color prev_side;  // side-to-move BEFORE this play, so undo() restores it exactly
                          // (needed for hypothetical out-of-turn plays during AI evaluation).
    };
    const std::vector<HistoryEntry>& history() const noexcept { return history_; }

private:
    std::array<Color, CELL_COUNT> cells_;
    std::vector<HistoryEntry> history_;
    Color side_;
    std::uint64_t hash_;
};

}  // namespace omok
