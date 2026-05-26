#include "omok/rules.hpp"

#include <array>

#include "omok/pattern.hpp"

namespace omok {

namespace {

using pattern::Line;

// Helper: scan the 4 directions from `m`, computing line analyses with `m` virtually placed.
struct DirectionAnalysis {
    Line line;
    bool has_four = false;
    std::array<int, 9> open_three_completions{};
    int num_open_three_completions = 0;
};

}  // namespace

bool RuleChecker::is_winning_move(const Board& b, Move m, Color c) const {
    if (!m.in_bounds()) return false;
    if (b.at(m) != Color::Empty) return false;
    if (c != Color::Black && c != Color::White) return false;

    for (Dir d : DIRECTIONS) {
        Line line = pattern::extract_line(b, m, c, d);
        line.v[Line::CENTER] = 1;  // virtually place
        if (c == Color::Black) {
            if (pattern::makes_exact_five_through_center(line)) return true;
            // overline does NOT win for black
        } else {
            if (pattern::makes_five_or_more_through_center(line)) return true;
        }
    }
    return false;
}

ForbiddenKind RuleChecker::classify_for_black(Board& b, Move m, int depth) const {
    if (depth > MAX_RECURSION_DEPTH) return ForbiddenKind::None;
    if (!m.in_bounds()) return ForbiddenKind::None;
    if (b.at(m) != Color::Empty) return ForbiddenKind::None;

    // Pre-analysis: collect direction info with m virtually placed.
    std::array<DirectionAnalysis, 4> infos{};
    bool makes_exact_five = false;
    bool makes_overline = false;
    int four_count = 0;

    for (size_t di = 0; di < DIRECTIONS.size(); ++di) {
        Dir d = DIRECTIONS[di];
        Line line = pattern::extract_line(b, m, Color::Black, d);
        line.v[Line::CENTER] = 1;
        int run = pattern::run_length_through_center(line);
        if (run == 5) makes_exact_five = true;
        if (run >= 6) makes_overline = true;
        infos[di].line = line;
        infos[di].has_four = pattern::line_has_four(line);
        if (infos[di].has_four) ++four_count;
        pattern::line_has_naive_open_three(line, &infos[di].open_three_completions,
                                           &infos[di].num_open_three_completions);
    }

    // Five wins, even if overline-like shape exists in another direction.
    if (makes_exact_five) return ForbiddenKind::None;
    if (makes_overline) return ForbiddenKind::Overline;
    if (four_count >= 2) return ForbiddenKind::DoubleFour;

    // Open-three counting with recursive validation. Each direction with at least one
    // legal open-four completion contributes one open three.
    int validated_open_threes = 0;

    // Actually play m on the board so the recursive call evaluates a state where m exists.
    b.play(m, Color::Black);

    for (size_t di = 0; di < DIRECTIONS.size(); ++di) {
        if (infos[di].num_open_three_completions == 0) continue;
        Dir d = DIRECTIONS[di];
        bool any_valid = false;
        for (int k = 0; k < infos[di].num_open_three_completions; ++k) {
            int window_idx = infos[di].open_three_completions[k];
            int offset = window_idx - Line::CENTER;
            Move e{static_cast<std::int8_t>(m.r + d.dr * offset),
                   static_cast<std::int8_t>(m.c + d.dc * offset)};
            if (!e.in_bounds()) continue;
            if (b.at(e) != Color::Empty) continue;
            ForbiddenKind sub = classify_for_black(b, e, depth + 1);
            if (sub == ForbiddenKind::None) {
                any_valid = true;
                break;
            }
        }
        if (any_valid) ++validated_open_threes;
    }

    b.undo();

    if (validated_open_threes >= 2) return ForbiddenKind::DoubleThree;
    return ForbiddenKind::None;
}

bool RuleChecker::last_move_wins(const Board& b) const {
    auto last = b.last_move();
    if (!last) return false;
    Color c = b.history().back().color;
    for (Dir d : DIRECTIONS) {
        int run = 1;
        for (int k = 1; k < 6; ++k) {
            int r = last->r + d.dr * k;
            int cc = last->c + d.dc * k;
            if (r < 0 || r >= BOARD_SIZE || cc < 0 || cc >= BOARD_SIZE) break;
            if (b.at(r, cc) == c) ++run;
            else break;
        }
        for (int k = 1; k < 6; ++k) {
            int r = last->r - d.dr * k;
            int cc = last->c - d.dc * k;
            if (r < 0 || r >= BOARD_SIZE || cc < 0 || cc >= BOARD_SIZE) break;
            if (b.at(r, cc) == c) ++run;
            else break;
        }
        if (c == Color::Black) {
            if (run == 5) return true;  // 6+ would be overline (forbidden), not a win
        } else {
            if (run >= 5) return true;
        }
    }
    return false;
}

std::vector<Move> RuleChecker::compute_forbidden_squares(Board& b, Color c) const {
    std::vector<Move> result;
    if (c != Color::Black) return result;
    for (int r = 0; r < BOARD_SIZE; ++r) {
        for (int col = 0; col < BOARD_SIZE; ++col) {
            Move m{static_cast<std::int8_t>(r), static_cast<std::int8_t>(col)};
            if (b.at(m) != Color::Empty) continue;
            if (classify_for_black(b, m) != ForbiddenKind::None) {
                result.push_back(m);
            }
        }
    }
    return result;
}

}  // namespace omok
