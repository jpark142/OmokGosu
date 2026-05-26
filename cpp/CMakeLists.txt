include(FetchContent)

# ---- omok_engine: header + sources library (static, no Python dep) ----
add_library(omok_engine STATIC
    src/board.cpp
    src/zobrist.cpp
    src/pattern.cpp
    src/rules.cpp
    src/eval.cpp
    src/movegen.cpp
    src/search.cpp
)
target_include_directories(omok_engine PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
set_target_properties(omok_engine PROPERTIES POSITION_INDEPENDENT_CODE ON)

# ---- pybind11 module ----
if(OMOK_BUILD_PYBIND)
    find_package(pybind11 CONFIG REQUIRED)
    pybind11_add_module(omok_core MODULE bindings/pybind_module.cpp)
    target_link_libraries(omok_core PRIVATE omok_engine)
    target_compile_definitions(omok_core PRIVATE OMOK_PYBIND_BUILD)
    install(TARGETS omok_core LIBRARY DESTINATION . RUNTIME DESTINATION .)
endif()

# ---- tests (doctest) ----
if(OMOK_BUILD_TESTS)
    FetchContent_Declare(
        doctest
        GIT_REPOSITORY https://github.com/doctest/doctest.git
        GIT_TAG v2.4.11
    )
    FetchContent_MakeAvailable(doctest)

    enable_testing()
    add_executable(omok_tests
        tests/test_main.cpp
        tests/test_board.cpp
        tests/test_pattern.cpp
        tests/test_rules.cpp
        tests/test_search.cpp
    )
    target_link_libraries(omok_tests PRIVATE omok_engine doctest::doctest)
    target_compile_definitions(omok_tests PRIVATE
        OMOK_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures"
    )
    add_test(NAME omok_tests COMMAND omok_tests)
endif()
