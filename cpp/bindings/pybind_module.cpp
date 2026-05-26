#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "omok/board.hpp"
#include "omok/eval.hpp"
#include "omok/rules.hpp"
#include "omok/search.hpp"
#include "omok/types.hpp"

namespace py = pybind11;
using namespace omok;

PYBIND11_MODULE(omok_core, m) {
    m.doc() = "OmokGosu C++ core engine: Board, RuleChecker, types.";

    py::enum_<Color>(m, "Color")
        .value("Empty", Color::Empty)
        .value("Black", Color::Black)
        .value("White", Color::White)
        .export_values();

    py::enum_<ForbiddenKind>(m, "ForbiddenKind")
        .value("Nothing", ForbiddenKind::None)  // 'None' clashes with Python None keyword
        .value("DoubleThree", ForbiddenKind::DoubleThree)
        .value("DoubleFour", ForbiddenKind::DoubleFour)
        .value("Overline", ForbiddenKind::Overline)
        .export_values();

    m.attr("BOARD_SIZE") = BOARD_SIZE;

    py::class_<Move>(m, "Move")
        .def(py::init([](int r, int c) {
                 return Move{static_cast<std::int8_t>(r), static_cast<std::int8_t>(c)};
             }),
             py::arg("r"), py::arg("c"))
        .def_readwrite("r", &Move::r)
        .def_readwrite("c", &Move::c)
        .def("in_bounds", &Move::in_bounds)
        .def("__repr__",
             [](const Move& m) { return "Move(" + std::to_string(m.r) + "," + std::to_string(m.c) + ")"; })
        .def("__eq__", [](const Move& a, const Move& b) { return a == b; })
        .def("__hash__", [](const Move& a) { return std::hash<int>{}(a.index()); });

    py::class_<Board>(m, "Board")
        .def(py::init<>())
        .def("reset", &Board::reset)
        .def("at", py::overload_cast<int, int>(&Board::at, py::const_))
        .def("play",
             [](Board& b, int r, int c, Color color) {
                 return b.play(Move{static_cast<std::int8_t>(r), static_cast<std::int8_t>(c)}, color);
             },
             py::arg("r"), py::arg("c"), py::arg("color"))
        .def("undo", &Board::undo)
        .def_property_readonly("move_count", &Board::move_count)
        .def_property_readonly("side_to_move", &Board::side_to_move)
        .def_property_readonly("hash", &Board::hash)
        .def("is_empty", &Board::is_empty)
        .def("last_move", &Board::last_move)
        .def("cells",
             [](const Board& b) {
                 const auto& cells = b.cells();
                 std::vector<int> out(cells.size());
                 for (size_t i = 0; i < cells.size(); ++i) out[i] = static_cast<int>(cells[i]);
                 return out;
             })
        .def("history",
             [](const Board& b) {
                 std::vector<std::tuple<int, int, int>> out;
                 for (const auto& e : b.history()) {
                     out.emplace_back(e.move.r, e.move.c, static_cast<int>(e.color));
                 }
                 return out;
             });

    py::class_<RuleChecker>(m, "RuleChecker")
        .def(py::init<>())
        .def("is_winning_move",
             [](const RuleChecker& rc, const Board& b, int r, int c, Color color) {
                 return rc.is_winning_move(b, Move{static_cast<std::int8_t>(r),
                                                   static_cast<std::int8_t>(c)},
                                           color);
             },
             py::arg("board"), py::arg("r"), py::arg("c"), py::arg("color"))
        .def("classify_for_black",
             [](const RuleChecker& rc, Board& b, int r, int c) {
                 return rc.classify_for_black(b, Move{static_cast<std::int8_t>(r),
                                                     static_cast<std::int8_t>(c)});
             },
             py::arg("board"), py::arg("r"), py::arg("c"))
        .def("last_move_wins", &RuleChecker::last_move_wins)
        .def("compute_forbidden_squares",
             [](const RuleChecker& rc, Board& b, Color c) {
                 auto v = rc.compute_forbidden_squares(b, c);
                 std::vector<std::pair<int, int>> out;
                 out.reserve(v.size());
                 for (auto& m : v) out.emplace_back(m.r, m.c);
                 return out;
             },
             py::arg("board"), py::arg("color"));

    m.def("evaluate",
          [](const Board& b, Color to_move) { return eval::evaluate(b, to_move); },
          py::arg("board"), py::arg("to_move"),
          "Static board evaluation from to_move's perspective. Positive = winning.");

    py::class_<search::SearchLimits>(m, "SearchLimits")
        .def(py::init<>())
        .def_readwrite("max_depth",   &search::SearchLimits::max_depth)
        .def_readwrite("budget_ms",   &search::SearchLimits::budget_ms)
        .def_readwrite("root_width",  &search::SearchLimits::root_width)
        .def_readwrite("child_width", &search::SearchLimits::child_width);

    py::class_<search::SearchResult>(m, "SearchResult")
        .def_property_readonly("best_r",
                               [](const search::SearchResult& r) { return int(r.best_move.r); })
        .def_property_readonly("best_c",
                               [](const search::SearchResult& r) { return int(r.best_move.c); })
        .def_readonly("score",      &search::SearchResult::score)
        .def_readonly("depth",      &search::SearchResult::depth)
        .def_readonly("nodes",      &search::SearchResult::nodes)
        .def_readonly("tt_hits",    &search::SearchResult::tt_hits)
        .def_readonly("elapsed_ms", &search::SearchResult::elapsed_ms)
        .def_readonly("aborted",    &search::SearchResult::aborted);

    py::class_<search::Searcher>(m, "Searcher")
        .def(py::init<std::size_t>(), py::arg("tt_size_mb") = 32)
        .def("clear",  &search::Searcher::clear)
        .def("search",
             [](search::Searcher& s, Board& b, Color to_move, const RuleChecker& rc,
                const search::SearchLimits& lim) {
                 py::gil_scoped_release release;
                 return s.search(b, to_move, rc, lim);
             },
             py::arg("board"), py::arg("to_move"), py::arg("rules"), py::arg("limits"),
             "Run iterative-deepening alpha-beta and return the SearchResult.");
}
