#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <atomic>
#include <csignal>
#include <sstream>
#include <iomanip>
#include <ctime>

#include "renderer.h"
#include "audio_engine.h"
#include "bridge_client.h"
#include "input_handler.h"
#include "live2d_model.h"

namespace {

std::atomic<bool> g_running{true};

void SignalHandler(int signum) {
    std::cout << "\n[Main] Signal " << signum << " received, shutting down..." << std::endl;
    g_running.store(false);
}

std::string Timestamp() {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    return oss.str();
}

void LogInit() {
    std::cout << "[" << Timestamp() << "] [Main] uPage-cpp v0.1.0 starting..." << std::endl;
}

void PrintUsage(const char* prog) {
    std::cout << "Usage: " << prog << " [options]\n"
              << "Options:\n"
              << "  -s, --server <addr>    Server address (default: localhost)\n"
              << "  -p, --port <port>      Server port (default: 50051)\n"
              << "  -w, --width <px>       Window width (default: 1280)\n"
              << "  -h, --height <px>      Window height (default: 720)\n"
              << "  --help                 Show this help\n";
}

struct CLIOptions {
    std::string server = "localhost";
    int port = 50051;
    int width = 1280;
    int height = 720;
};

CLIOptions ParseArgs(int argc, char* argv[]) {
    CLIOptions opts;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-s" || arg == "--server") {
            if (++i < argc) opts.server = argv[i];
        } else if (arg == "-p" || arg == "--port") {
            if (++i < argc) opts.port = std::stoi(argv[i]);
        } else if (arg == "-w" || arg == "--width") {
            if (++i < argc) opts.width = std::stoi(argv[i]);
        } else if (arg == "-h" || arg == "--height") {
            if (++i < argc) opts.height = std::stoi(argv[i]);
        } else if (arg == "--help") {
            PrintUsage(argv[0]);
            exit(0);
        }
    }
    return opts;
}

void ConnectionMonitor(upage::BridgeClient& bridge) {
    int fail_count = 0;
    while (g_running.load()) {
        if (!bridge.IsConnected()) {
            ++fail_count;
            std::cerr << "[" << Timestamp() << "] [Main] Connection lost (attempt " << fail_count << ")" << std::endl;
        } else {
            fail_count = 0;
        }
        std::this_thread::sleep_for(std::chrono::seconds(5));
    }
}

void InteractiveLoop(upage::BridgeClient& bridge, upage::AudioEngine& audio) {
    std::cout << "[Main] Interactive loop started. Type messages and press Enter." << std::endl;
    std::cout << "[Main] Commands: /quit (exit), /vol <0-100> (volume)" << std::endl;

    std::string line;
    while (g_running.load()) {
        std::cout << "> " << std::flush;
        if (!std::getline(std::cin, line)) break;
        if (line.empty()) continue;

        if (line == "/quit") {
            g_running.store(false);
            break;
        }

        if (line.rfind("/vol ", 0) == 0) {
            try {
                float vol = std::stof(line.substr(5)) / 100.0f;
                audio.SetVolume(std::clamp(vol, 0.0f, 1.0f));
                std::cout << "[Main] Volume set to " << static_cast<int>(vol * 100) << "%" << std::endl;
            } catch (...) {
                std::cerr << "[Main] Invalid volume" << std::endl;
            }
            continue;
        }

        upage::ChatInput input;
        input.user_id = "user";
        input.message = line;
        input.session_id = "session_001";

        auto reply = bridge.ProcessChat(input);

        if (!reply.reply_text.empty()) {
            std::cout << "[AI] " << reply.reply_text << std::endl;
            if (!reply.emotion.empty()) {
                std::cout << "[Emotion] " << reply.emotion << std::endl;
            }
            bridge.StreamAudio(reply.reply_text, [&](const std::vector<float>& samples) {
                audio.PlayStream(samples, 24000);
            });
        }
    }
}

} // anonymous namespace

int main(int argc, char* argv[]) {
    LogInit();

    auto opts = ParseArgs(argc, argv);

    std::signal(SIGINT, SignalHandler);
    std::signal(SIGTERM, SignalHandler);

    std::string server_addr = opts.server + ":" + std::to_string(opts.port);
    std::cout << "[Main] Connecting to server: " << server_addr << std::endl;

    upage::BridgeClient bridge(server_addr);
    upage::AudioEngine audio;
    upage::Renderer renderer;
    upage::InputHandler input_handler;
    upage::Live2DModel live2d;

    if (!renderer.Init(opts.width, opts.height, "uPage Virtual Human")) {
        std::cerr << "[" << Timestamp() << "] [Main] Failed to initialize renderer" << std::endl;
        return 1;
    }

    if (!audio.Init()) {
        std::cerr << "[" << Timestamp() << "] [Main] Failed to initialize audio" << std::endl;
        return 1;
    }

    if (!live2d.Load("models/default.model3.json")) {
        std::cerr << "[" << Timestamp() << "] [Main] Failed to load Live2D model" << std::endl;
    }

    std::thread monitor(ConnectionMonitor, std::ref(bridge));
    std::thread interactive(InteractiveLoop, std::ref(bridge), std::ref(audio));

    renderer.Run();
    g_running.store(false);

    if (interactive.joinable()) interactive.join();
    if (monitor.joinable()) monitor.join();

    renderer.Shutdown();
    std::cout << "[" << Timestamp() << "] [Main] Shutdown complete" << std::endl;
    return 0;
}
