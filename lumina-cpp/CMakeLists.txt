cmake_minimum_required(VERSION 3.20)
project(lumina-cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Options ──────────────────────────────────────
option(LUMINA_USE_LIVE2D "Build with Live2D support" ON)
option(LUMINA_USE_GRPC "Build with gRPC support" ON)
option(LUMINA_BUILD_GRPC_ONLY
    "CI-only: build only gRPC client (no OpenGL/Live2D/OpenAL)"
    OFF)

# ── External dependencies ────────────────────────
find_package(OpenGL QUIET)
find_package(OpenAL QUIET)
find_package(GLFW3 QUIET)

if(LUMINA_USE_GRPC OR LUMINA_BUILD_GRPC_ONLY)
    find_package(gRPC QUIET)
    find_package(Protobuf QUIET)
endif()

if(LUMINA_USE_LIVE2D)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/external/live2d-cubism/CMakeLists.txt)
        add_subdirectory(external/live2d-cubism)
    endif()
endif()

# ── Proto ────────────────────────────────────────
if(NOT LUMINA_BUILD_GRPC_ONLY)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto/CMakeLists.txt)
        add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto
            ${CMAKE_CURRENT_BINARY_DIR}/lumina-proto)
    endif()
endif()

if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto/build)
    set(LUMINA_PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto)
elseif(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto)
    set(LUMINA_PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto)
    message(STATUS "lumina-proto found but build/ dir missing — proto stubs may be absent")
else()
    set(LUMINA_PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../lumina-proto)
    message(STATUS "lumina-proto not found at ${LUMINA_PROTO_DIR}")
endif()

# ── Source files ─────────────────────────────────
set(LUMINA_SOURCES
    src/main.cpp
    src/renderer.cpp
    src/audio_engine.cpp
    src/live2d_model.cpp
    src/input_handler.cpp
    src/grpc_client.cpp
    src/lip_sync_handler.cpp
)

set(LUMINA_GRPC_ONLY_SOURCES
    src/grpc_client.cpp
)

# ── Target: full client ──────────────────────────
if(NOT LUMINA_BUILD_GRPC_ONLY)
    add_executable(lumina_client ${LUMINA_SOURCES})

    target_include_directories(lumina_client PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${LUMINA_PROTO_DIR}/build
        ${LUMINA_PROTO_DIR}/src
    )

    if(OpenGL_FOUND)
        target_link_libraries(lumina_client PRIVATE OpenGL::GL)
        target_compile_definitions(lumina_client PRIVATE LUMINA_HAS_OPENGL)
    endif()

    if(GLFW3_FOUND)
        target_link_libraries(lumina_client PRIVATE glfw)
        target_compile_definitions(lumina_client PRIVATE LUMINA_HAS_GLFW)
    endif()

    if(OpenAL_FOUND)
        target_link_libraries(lumina_client PRIVATE OpenAL::AL)
        target_compile_definitions(lumina_client PRIVATE LUMINA_HAS_OPENAL)
    endif()

    if(gRPC_FOUND AND Protobuf_FOUND)
        target_link_libraries(lumina_client PRIVATE gRPC::grpc++ protobuf::libprotobuf)
        target_compile_definitions(lumina_client PRIVATE LUMINA_HAS_GRPC)
    endif()

    if(LUMINA_USE_LIVE2D AND TARGET live2d-cubism)
        target_link_libraries(lumina_client PRIVATE live2d-cubism)
        target_compile_definitions(lumina_client PRIVATE LUMINA_HAS_LIVE2D)
    endif()

    if(WIN32)
        target_link_libraries(lumina_client PRIVATE
            strmiids ole32 oleaut32
        )
    endif()

    target_compile_definitions(lumina_client PRIVATE
        $<$<CONFIG:Debug>:LUMINA_DEBUG>
    )
endif()

# ── Target: minimal gRPC-only (CI) ──────────────
if(LUMINA_BUILD_GRPC_ONLY)
    add_executable(lumina_grpc_check ${LUMINA_GRPC_ONLY_SOURCES})

    target_include_directories(lumina_grpc_check PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${LUMINA_PROTO_DIR}/build
        ${LUMINA_PROTO_DIR}/src
    )

    if(gRPC_FOUND AND Protobuf_FOUND)
        target_link_libraries(lumina_grpc_check PRIVATE
            gRPC::grpc++ protobuf::libprotobuf
        )
        target_compile_definitions(lumina_grpc_check PRIVATE
            LUMINA_HAS_GRPC
        )
        message(STATUS "gRPC check target: lumina_grpc_check")
    else()
        message(WARNING
            "gRPC/Protobuf not found — lumina_grpc_check will not link. "
            "Install libgrpc-dev and libprotobuf-dev."
        )
    endif()
endif()
