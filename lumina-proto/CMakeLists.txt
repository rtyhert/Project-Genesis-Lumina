cmake_minimum_required(VERSION 3.20)
project(lumina-proto VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(PROTO_SRC "${CMAKE_CURRENT_SOURCE_DIR}/src/lumina.proto")
set(PROTO_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}")

# --- Proto file copy to build dir ---
configure_file("${PROTO_SRC}" "${PROTO_BUILD_DIR}/lumina.proto" COPYONLY)

# --- Generate gRPC C++ stubs ---
set(PROTO_SRCS "${PROTO_BUILD_DIR}/lumina.pb.cc")
set(PROTO_HDRS "${PROTO_BUILD_DIR}/lumina.pb.h")
set(GRPC_SRCS "${PROTO_BUILD_DIR}/lumina.grpc.pb.cc")
set(GRPC_HDRS "${PROTO_BUILD_DIR}/lumina.grpc.pb.h")

add_custom_command(
    OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND Protobuf::protoc
        -I "${CMAKE_CURRENT_SOURCE_DIR}/src"
        --cpp_out "${PROTO_BUILD_DIR}"
        --grpc_out "${PROTO_BUILD_DIR}"
        --plugin=protoc-gen-grpc="$<TARGET_FILE:gRPC::grpc_cpp_plugin>"
        "${PROTO_BUILD_DIR}/lumina.proto"
    DEPENDS "${PROTO_SRC}"
    COMMENT "[lumina-proto] Generating C++ stubs from lumina.proto"
    VERBATIM
)

# --- Static library target ---
add_library(lumina_proto STATIC
    "${PROTO_SRCS}"
    "${GRPC_SRCS}"
)

target_include_directories(lumina_proto PUBLIC
    $<BUILD_INTERFACE:${PROTO_BUILD_DIR}>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(lumina_proto PUBLIC
    protobuf::libprotobuf
    gRPC::grpc++
    gRPC::grpc++_reflection
)

# --- Ensure protobuf and gRPC headers are findable ---
target_include_directories(lumina_proto SYSTEM PUBLIC
    ${Protobuf_INCLUDE_DIRS}
    ${gRPC_INCLUDE_DIRS}
)

set_target_properties(lumina_proto PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
)
