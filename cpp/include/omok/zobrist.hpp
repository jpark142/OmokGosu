#pragma once

#include <array>
#include <cstdint>

#include "omok/types.hpp"

namespace omok {

// 2 colors × 225 squares of 64-bit keys. side_to_move key flips on each turn.
class Zobrist {
public:
    static const Zobrist& instance();

    std::uint64_t piece_key(Color c, int idx) const noexcept;
    std::uint64_t side_to_move_key() const noexcept { return side_; }

private:
    Zobrist();
    std::array<std::array<std::uint64_t, CELL_COUNT>, 2> keys_;  // [0]=Black, [1]=White
    std::uint64_t side_;
};

}  // namespace omok
