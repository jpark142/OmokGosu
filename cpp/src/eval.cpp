#include "omok/eval.hpp"

#include <algorithm>
#include <array>

namespace omok::eval {

namespace {

// Classify a single contiguous run of `my` stones in a 1-D line.
//   run_len: number of consecutive own stones
//   left_open, right_open: true iff the bordering cell is Empty (not opp, not wall)
//   is_black: whether this run is for black (so 6+ becomes overline penalty, not 5-win)
// Returns the weight contribution.
int classify_run(int run_len, bool left_open, bool right_open, bool is_black,
                 const Weights& w) {
    if (run_len >= 6) {
        return is_black ? w.overline_black : w.five;
    }
    if (run_len == 5) return w.five;

    int openings = (left_open ? 1 : 0) + (right_open ? 1 : 0);
    if (openings == 0) return 0;  // fully blocked run < 5: dead

    if (run_len == 4) return (openings == 2) ? w.open_four : w.four;
    if (run_len == 3) return (openings == 2) ? w.open_three : w.closed_three;
    if (run_len == 2) return (openings == 2) ? w.open_two : w.closed_two;
    return 0;  // run_len == 1: too weak to score on its own
}

// Score all runs of `my` along a single line of cells (length up to 15).
int score_line(const std::array<int, BOARD_SIZE>& cells, int len, int my, bool is_black,
               const Weights& w) {
    int total = 0;
    int i = 0;
    while (i < len) {
        if (cells[i] == my) {
            int j = i;
            while (j < len && cells[j] == my) ++j;
            int run = j - i;
            bool left_open  = (i > 0) && (cells[i - 1] == 0);
            bool right_open = (j < len) && (cells[j] == 0);
            total += classify_run(run, left_open, right_open, is_black, w);
            i = j;
        } else {
            ++i;
        }
    }
    return total;
}

}  // namespace

int score_for(const Board& b, Color c, const Weights& w) {
    if (c != Color::Black && c != Color::White) return 0;
    int my = static_cast<int>(c);
    bool is_black = (c == Color::Black);
    int total = 0;
    std::array<int, BOARD_SIZE> line{};

    // Rows
    for (int r = 0; r < BOARD_SIZE; ++r) {
        for (int col = 0; col < BOARD_SIZE; ++col) {
            line[col] = static_cast<int>(b.at(r, col));
        }
        total += score_line(line, BOARD_SIZE, my, is_black, w);
    }
    // Columns
    for (int col = 0; col < BOARD_SIZE; ++col) {
        for (int r = 0; r < BOARD_SIZE; ++r) {
            line[r] = static_cast<int>(b.at(r, col));
        }
        total += score_line(line, BOARD_SIZE, my, is_black, w);
    }
    // Diagonals (dr=1, dc=1): starts at top row and left column.
    for (int start_r = 0; start_r < BOARD_SIZE; ++start_r) {
        int len = 0;
        int r = start_r, col = 0;
        while (r < BOARD_SIZE && col < BOARD_SIZE) {
            line[len++] = static_cast<int>(b.at(r, col));
            ++r;
            ++col;
        }
        if (len >= 5) total += score_line(line, len, my, is_black, w);
    }
    for (int start_c = 1; start_c < BOARD_SIZE; ++start_c) {
        int len = 0;
        int r = 0, col = start_c;
        while (r < BOARD_SIZE && col < BOARD_SIZE) {
            line[len++] = static_cast<int>(b.at(r, col));
            ++r;
            ++col;
        }
        if (len >= 5) total += score_line(line, len, my, is_black, w);
    }
    // Anti-diagonals (dr=1, dc=-1): starts at top row (right→left) and right column.
    for (int start_c = 0; start_c < BOARD_SIZE; ++start_c) {
        int len = 0;
        int r = 0, col = start_c;
        while (r < BOARD_SIZE && col >= 0) {
            line[len++] = static_cast<int>(b.at(r, col));
            ++r;
            --col;
        }
        if (len >= 5) total += score_line(line, len, my, is_black, w);
    }
    for (int start_r = 1; start_r < BOARD_SIZE; ++start_r) {
        int len = 0;
        int r = start_r, col = BOARD_SIZE - 1;
        while (r < BOARD_SIZE && col >= 0) {
            line[len++] = static_cast<int>(b.at(r, col));
            ++r;
            --col;
        }
        if (len >= 5) total += score_line(line, len, my, is_black, w);
    }
    return total;
}

int evaluate(const Board& b, Color to_move, const Weights& w) {
    if (to_move != Color::Black && to_move != Color::White) return 0;
    Color opp = opponent(to_move);
    int me = score_for(b, to_move, w);
    int they = score_for(b, opp, w);
    int diff = me - they;
    if (diff > WIN) diff = WIN;
    if (diff < -WIN) diff = -WIN;
    return diff;
}

}  // namespace omok::eval
