cmake_minimum_required(VERSION 3.20)
project(DietOptimizerCpp20 VERSION 0.1.0 LANGUAGES CXX)

include(CTest)
find_package(PkgConfig REQUIRED)
pkg_check_modules(NLOPT REQUIRED IMPORTED_TARGET nlopt_cxx=2.7.1)
# OSQP v1.0.0's installed config currently advertises package version 0.0.0.
# The Makefile and CI pin the source tag; CMake's package version check would
# reject that correctly built installation.
find_package(osqp CONFIG REQUIRED)

add_executable(diet_optimizer
    src/main.cpp
    src/model.cpp
    src/osqp_audit.cpp
)
target_compile_features(diet_optimizer PRIVATE cxx_std_20)
target_include_directories(diet_optimizer PRIVATE include)
target_link_libraries(diet_optimizer PRIVATE PkgConfig::NLOPT osqp::osqp)

if(MSVC)
    target_compile_options(diet_optimizer PRIVATE /W4 /permissive-)
else()
    target_compile_options(diet_optimizer PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)

    add_executable(model_regression_tests
        tests/model_regression.cpp
        src/model.cpp
    )
    target_compile_features(model_regression_tests PRIVATE cxx_std_20)
    target_include_directories(model_regression_tests PRIVATE include)

    if(MSVC)
        target_compile_options(model_regression_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(model_regression_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME model_regression COMMAND model_regression_tests)
    add_test(NAME optimizer_sparse_regression
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_optimizer_output.py
                $<TARGET_FILE:diet_optimizer> --sparse)
    add_test(NAME optimizer_diverse_regression
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_optimizer_output.py
                $<TARGET_FILE:diet_optimizer> --diverse)
endif()
