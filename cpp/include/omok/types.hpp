#pragma once

#include <array>
#include <cstdint>
#include <string_view>

namespace omok {

constexpr int BOARD_SIZE = 15;
constexpr int CELL_COUNT = BOARD_SIZE * BOARD_SIZE;

enum class Color : std::uint8_t {
    Empty = 0,
    Black = 1,
    White = 2,
};

constexpr Color opponent(Color c) noexcept {
    if (c == Color::Black) return Color::White;
    if (c == Color::White) return Color::Black;
    return Color::Empty;
}

constexpr std::string_view color_name(Color c) noexcept {
    switch (c) {
        case Color::Black: return "BLACK";
        case Color::White: return "WHITE";
        case Color::Empty: return "EMPTY";
    }
    return "?";
}

struct Move {
    std::int8_t r;  // 0..14
    std::int8_t c;  // 0..14

    constexpr bool operator==(const Move& o) const noexcept = default;
    constexpr int index() const noexcept { return r * BOARD_SIZE + c; }
    static constexpr Move from_index(int i) noexcept {
        return Move{static_cast<std::int8_t>(i / BOARD_SIZE),
                    static_cast<std::int8_t>(i % BOARD_SIZE)};
    }
    constexpr bool in_bounds() const noexcept {
        return r >= 0 && r < BOARD_SIZE && c >= 0 && c < BOARD_SIZE;
    }
};

// Four scan directions: horizontal, vertical, diagonal-down-right, diagonal-up-right.
struct Dir {
    std::int8_t dr;
    std::int8_t dc;
};
inline constexpr std::array<Dir, 4> DIRECTIONS = {{
    {0, 1},
    {1, 0},
    {1, 1},
    {1, -1},
}};

// Reason a move was rejected or marked forbidden.
enum class ForbiddenKind : std::uint8_t {
    None = 0,
    DoubleThree,
    DoubleFour,
    Overline,
};

constexpr std::string_view forbidden_name(ForbiddenKind k) noexcept {
    switch (k) {
        case ForbiddenKind::None:        return "NONE";
        case ForbiddenKind::DoubleThree: return "DOUBLE_THREE";
        case ForbiddenKind::DoubleFour:  return "DOUBLE_FOUR";
        case ForbiddenKind::Overline:    return "OVERLINE";
    }
    return "?";
}

}  // namespace omok
