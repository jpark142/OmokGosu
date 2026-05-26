#include "omok/pattern.hpp"

namespace omok::pattern {

namespace {

inline int encode_cell(Color cell, Color my) {
    if (cell == Color::Empty) return 0;
    if (cell == my) return 1;
    return 2;  // opponent
}

}  // namespace

Line extract_line(const Board& b, Move m, Color my, Dir d) {
    Line line;
    for (int k = -Line::CENTER; k <= Line::CENTER; ++k) {
        int r = m.r + d.dr * k;
        int c = m.c + d.dc * k;
        int idx = k + Line::CENTER;
        if (r < 0 || r >= BOARD_SIZE || c < 0 || c >= BOARD_SIZE) {
            line.v[idx] = 3;  // wall
        } else {
            line.v[idx] = encode_cell(b.at(r, c), my);
        }
    }
    return line;
}

int run_length_through_center(const Line& line) {
    if (line.v[Line::CENTER] != 1) return 0;
    int len = 1;
    for (int i = Line::CENTER - 1; i >= 0 && line.v[i] == 1; --i) ++len;
    for (int i = Line::CENTER + 1; i < Line::LEN && line.v[i] == 1; ++i) ++len;
    return len;
}

bool makes_five_or_more_through_center(const Line& line) {
    return run_length_through_center(line) >= 5;
}

bool makes_exact_five_through_center(const Line& line) {
    return run_length_through_center(line) == 5;
}

bool makes_overline_through_center(const Line& line) {
    return run_length_through_center(line) >= 6;
}

bool line_has_four(const Line& line, std::array<int, 9>* completions, int* num_completions) {
    if (completions) completions->fill(-1);
    if (num_completions) *num_completions = 0;
    if (line.v[Line::CENTER] != 1) return false;

    int n = 0;
    for (int i = 0; i < Line::LEN; ++i) {
        if (line.v[i] != 0) continue;       // must be empty
        Line t = line;
        t.v[i] = 1;
        // After placing mine at i, does a 5-in-a-row through center exist?
        if (run_length_through_center(t) >= 5) {
            if (completions && n < 9) (*completions)[n] = i;
            ++n;
        }
    }
    if (num_completions) *num_completions = n;
    return n > 0;
}

bool line_has_naive_open_three(const Line& line, std::array<int, 9>* completions,
                               int* num_completions) {
    if (completions) completions->fill(-1);
    if (num_completions) *num_completions = 0;
    if (line.v[Line::CENTER] != 1) return false;

    int n = 0;
    for (int i = 0; i < Line::LEN; ++i) {
        if (i == Line::CENTER) continue;
        if (line.v[i] != 0) continue;
        Line t = line;
        t.v[i] = 1;
        // Find run containing center in t.
        if (t.v[Line::CENTER] != 1) continue;
        int start = Line::CENTER, end = Line::CENTER;
        while (start > 0 && t.v[start - 1] == 1) --start;
        while (end < Line::LEN - 1 && t.v[end + 1] == 1) ++end;
        int len = end - start + 1;
        if (len != 4) continue;  // need exactly 4 to be an open four
        // Both immediate neighbors must be empty (0). Wall (3) or opponent (2) blocks open four.
        bool left_open = (start > 0) && (t.v[start - 1] == 0);
        bool right_open = (end < Line::LEN - 1) && (t.v[end + 1] == 0);
        if (!left_open || !right_open) continue;
        // Also: this should not be an overline-in-disguise. By construction len==4, so safe.
        if (completions && n < 9) (*completions)[n] = i;
        ++n;
    }
    if (num_completions) *num_completions = n;
    return n > 0;
}

}  // namespace omok::pattern
