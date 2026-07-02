# Build and test configuration for C++ tests
cmake_minimum_required(VERSION 3.20)

project(lumina-cpp-test LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Fetch Google Test ────────────────────────────
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.15.2
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# ── Core logic tests (no GPU/hardware required) ──
set(CORE_TEST_SOURCES
    test_lip_sync.cpp
    test_live2d_model.cpp
    test_input_handler.cpp
)

set(CORE_SOURCES
    ../src/lip_sync_handler.cpp
    ../src/live2d_model.cpp
    ../src/input_handler.cpp
)

add_executable(lumina_core_test ${CORE_TEST_SOURCES} ${CORE_SOURCES})

target_include_directories(lumina_core_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${gtest_SOURCE_DIR}/include
)

target_link_libraries(lumina_core_test PRIVATE
    gtest
    gtest_main
    pthread
)

# ── Proto ────────────────────────────────────────
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/../../lumina-proto/build)
    set(LUMINA_PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../lumina-proto)
endif()

# ── gRPC tests (require proto stubs) ─────────────
if(gRPC_FOUND AND Protobuf_FOUND AND DEFINED LUMINA_PROTO_DIR)
    set(GRPC_TEST_SOURCES
        test_bridge_client.cpp
        test_grpc_client.cpp
    )

    set(GRPC_MOCK_SOURCES
        ../src/grpc_client.cpp
    )

    add_executable(lumina_grpc_test ${GRPC_TEST_SOURCES} ${GRPC_MOCK_SOURCES})

    target_include_directories(lumina_grpc_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../include
        ${LUMINA_PROTO_DIR}/build
        ${LUMINA_PROTO_DIR}/src
        ${gtest_SOURCE_DIR}/include
    )

    target_link_libraries(lumina_grpc_test PRIVATE
        gRPC::grpc++
        protobuf::libprotobuf
        gtest
        gtest_main
        pthread
    )

    target_compile_definitions(lumina_grpc_test PRIVATE LUMINA_HAS_GRPC)
endif()

# ── CTest integration ────────────────────────────
include(GoogleTest)
if(TARGET lumina_core_test)
    gtest_discover_tests(lumina_core_test)
endif()
if(TARGET lumina_grpc_test)
    gtest_discover_tests(lumina_grpc_test)
endif()
