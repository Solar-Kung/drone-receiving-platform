cmake_minimum_required(VERSION 3.16)
project(telemetry_publisher VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Zero-warning policy
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ── WP2: yaml-cpp ──────────────────────────────────────────────────────────────
find_package(yaml-cpp CONFIG REQUIRED)

# ── WP3: Protobuf ──────────────────────────────────────────────────────────────
find_package(Protobuf CONFIG REQUIRED)

# Generate protobuf C++ bindings from proto/telemetry.proto
file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/proto_gen)
add_custom_command(
    OUTPUT  ${CMAKE_CURRENT_BINARY_DIR}/proto_gen/telemetry.pb.cc
            ${CMAKE_CURRENT_BINARY_DIR}/proto_gen/telemetry.pb.h
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
            --proto_path=${CMAKE_CURRENT_SOURCE_DIR}/proto
            --cpp_out=${CMAKE_CURRENT_BINARY_DIR}/proto_gen
            ${CMAKE_CURRENT_SOURCE_DIR}/proto/telemetry.proto
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/proto/telemetry.proto
    COMMENT "Generating protobuf C++ code from telemetry.proto"
)

# ── WP4: spdlog + CLI11 ────────────────────────────────────────────────────────
find_package(spdlog CONFIG REQUIRED)
find_package(CLI11 CONFIG REQUIRED)

# ── Libraries ──────────────────────────────────────────────────────────────────

# Config + Trajectory (WP2)
add_library(tp_core
    src/config.cpp
    src/trajectory.cpp
)
target_include_directories(tp_core PUBLIC include)
target_link_libraries(tp_core PUBLIC yaml-cpp::yaml-cpp)

# Protobuf generated code (WP3)
add_library(tp_proto
    ${CMAKE_CURRENT_BINARY_DIR}/proto_gen/telemetry.pb.cc
)
target_include_directories(tp_proto PUBLIC ${CMAKE_CURRENT_BINARY_DIR}/proto_gen)
target_link_libraries(tp_proto PUBLIC protobuf::libprotobuf)

# UDP socket (WP3)
add_library(tp_udp src/udp_socket.cpp)
target_include_directories(tp_udp PUBLIC include)
target_link_libraries(tp_udp PUBLIC tp_proto spdlog::spdlog)

# Telemetry generator (WP3)
add_library(tp_generator src/telemetry_generator.cpp)
target_include_directories(tp_generator PUBLIC include)
target_link_libraries(tp_generator PUBLIC tp_core tp_proto spdlog::spdlog)

# Publisher (WP4)
add_library(tp_publisher src/publisher.cpp)
target_include_directories(tp_publisher PUBLIC include)
target_link_libraries(tp_publisher PUBLIC tp_core tp_udp tp_generator spdlog::spdlog)

# ── Main executable ────────────────────────────────────────────────────────────
add_executable(telemetry_publisher src/main.cpp)
target_link_libraries(telemetry_publisher PRIVATE
    tp_publisher
    spdlog::spdlog
    CLI11::CLI11
)

# ── Tests ──────────────────────────────────────────────────────────────────────
enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(test_trajectory tests/test_trajectory.cpp)
target_link_libraries(test_trajectory PRIVATE tp_core GTest::gtest_main)
add_test(NAME test_trajectory COMMAND test_trajectory)

add_executable(test_udp_socket tests/test_udp_socket.cpp)
target_link_libraries(test_udp_socket PRIVATE tp_udp GTest::gtest_main)
add_test(NAME test_udp_socket COMMAND test_udp_socket)

add_executable(test_telemetry_generator tests/test_telemetry_generator.cpp)
target_link_libraries(test_telemetry_generator PRIVATE tp_generator tp_core GTest::gtest_main)
add_test(NAME test_telemetry_generator COMMAND test_telemetry_generator)
