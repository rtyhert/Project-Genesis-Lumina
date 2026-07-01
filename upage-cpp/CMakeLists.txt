cmake_minimum_required(VERSION 3.20)
project(upage-cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenGL REQUIRED)
find_package(gRPC REQUIRED)
find_package(Protobuf REQUIRED)
find_package(OpenAL REQUIRED OPTIONAL)

add_subdirectory(external/live2d-cubism)
add_subdirectory(external/glfw)
add_subdirectory(upage-proto)

add_executable(upage_client
    src/main.cpp
    src/renderer.cpp
    src/audio_engine.cpp
    src/live2d_model.cpp
    src/input_handler.cpp
    src/grpc_client.cpp
)

target_include_directories(upage_client PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_BINARY_DIR}/../upage-proto
)

target_link_libraries(upage_client PRIVATE
    OpenGL::GL
    glfw
    live2d-cubism
    gRPC::grpc++
    protobuf::libprotobuf
    OpenAL::AL
)
