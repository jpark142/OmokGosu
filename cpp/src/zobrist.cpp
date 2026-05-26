#include "omok/zobrist.hpp"

#include <random>

namespace omok {

Zobrist::Zobrist() {
    // Deterministic seed → reproducible hashes across runs.
    std::mt19937_64 rng(0x9E3779B97F4A7C15ULL);
    for (auto& plane : keys_) {
        for (auto& k : plane) k = rng();
    }
    side_ = rng();
}

const Zobrist& Zobrist::instance() {
    static const Zobrist z;
    return z;
}

std::uint64_t Zobrist::piece_key(Color c, int idx) const noexcept {
    if (c == Color::Black) return keys_[0][idx];
    if (c == Color::White) return keys_[1][idx];
    return 0ULL;
}

}  // namespace omok
