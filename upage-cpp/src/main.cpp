#include <iostream>
#include <string>
#include <thread>
#include <chrono>

#include "renderer.h"
#include "audio_engine.h"
#include "bridge_client.h"

int main(int argc, char* argv[]) {
    std::cout << "=== upage-cpp v0.1.0 ===" << std::endl;

    std::string server_addr = "localhost:50051";
    if (argc > 1) {
        server_addr = argv[1];
    }

    upage::BridgeClient bridge(server_addr);
    upage::AudioEngine audio;
    upage::Renderer renderer;

    if (!renderer.Init(1280, 720, "uPage Virtual Human")) {
        std::cerr << "Failed to initialize renderer" << std::endl;
        return 1;
    }
    if (!audio.Init()) {
        std::cerr << "Failed to initialize audio" << std::endl;
        return 1;
    }

    renderer.Run();
    renderer.Shutdown();
    return 0;
}
