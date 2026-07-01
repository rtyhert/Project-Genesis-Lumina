#include "renderer.h"
#include <iostream>

namespace upage {

Renderer::Renderer() = default;
Renderer::~Renderer() = default;

bool Renderer::Init(int width, int height, const std::string& title) {
    std::cout << "[Renderer] Initializing " << width << "x" << height << " \"" << title << "\"" << std::endl;
    running_ = true;
    return true;
}

void Renderer::Run() {
    std::cout << "[Renderer] Entering main loop" << std::endl;
    while (running_) {
        HandleInput();
        if (model_) {
            model_->Update(0.016f);
            model_->Render();
        }
        RenderFrame();
    }
}

void Renderer::Shutdown() {
    running_ = false;
    std::cout << "[Renderer] Shutdown" << std::endl;
}

void Renderer::RenderFrame() {
    // OpenGL clear and swap buffers
}

void Renderer::HandleInput() {
    // GLFW input polling
}

} // namespace upage
