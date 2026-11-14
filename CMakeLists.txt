cmake_minimum_required(VERSION 3.20)
project(DietOptimizerCpp20 VERSION 0.1.0 LANGUAGES CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(NLOPT REQUIRED IMPORTED_TARGET nlopt_cxx)

add_executable(diet_optimizer
    src/main.cpp
    src/model.cpp
)
target_compile_features(diet_optimizer PRIVATE cxx_std_20)
target_include_directories(diet_optimizer PRIVATE include)
target_link_libraries(diet_optimizer PRIVATE PkgConfig::NLOPT)

if(MSVC)
    target_compile_options(diet_optimizer PRIVATE /W4 /permissive-)
else()
    target_compile_options(diet_optimizer PRIVATE -Wall -Wextra -Wpedantic)
endif()
