#include "omok/board.hpp"

#include "omok/zobrist.hpp"

namespace omok {

Board::Board() { reset(); }

void Board::reset() {
    cells_.fill(Color::Empty);
    history_.clear();
    side_ = Color::Black;
    hash_ = 0ULL;
}

Color Board::at(int r, int c) const noexcept {
    if (r < 0 || r >= BOARD_SIZE || c < 0 || c >= BOARD_SIZE) return Color::Empty;
    return cells_[r * BOARD_SIZE + c];
}

bool Board::is_empty(int r, int c) const noexcept {
    return r >= 0 && r < BOARD_SIZE && c >= 0 && c < BOARD_SIZE
           && cells_[r * BOARD_SIZE + c] == Color::Empty;
}

bool Board::play(Move m, Color c) noexcept {
    if (!m.in_bounds()) return false;
    int idx = m.index();
    if (cells_[idx] != Color::Empty) return false;
    if (c != Color::Black && c != Color::White) return false;

    cells_[idx] = c;
    history_.push_back({m, c, side_});  // record side BEFORE rotation
    const auto& z = Zobrist::instance();
    hash_ ^= z.piece_key(c, idx);
    hash_ ^= z.side_to_move_key();
    side_ = opponent(c);
    return true;
}

void Board::undo() noexcept {
    if (history_.empty()) return;
    auto last = history_.back();
    history_.pop_back();
    int idx = last.move.index();
    cells_[idx] = Color::Empty;
    const auto& z = Zobrist::instance();
    hash_ ^= z.piece_key(last.color, idx);
    hash_ ^= z.side_to_move_key();
    side_ = last.prev_side;  // restore exact prior side (handles out-of-turn plays correctly)
}

std::optional<Move> Board::last_move() const noexcept {
    if (history_.empty()) return std::nullopt;
    return history_.back().move;
}

}  // namespace omok
