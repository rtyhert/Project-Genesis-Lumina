#include "renderer.h"
#include <iostream>

#ifdef LUMINA_HAS_GLFW
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#include <GL/gl.h>
#endif

namespace lumina {

Renderer::Renderer() = default;

Renderer::~Renderer() {
    Shutdown();
}

bool Renderer::Init(int width, int height, const std::string& title) {
#ifdef LUMINA_HAS_GLFW
    if (!glfwInit()) {
        std::cerr << "[Renderer] Failed to initialize GLFW" << std::endl;
        return false;
    }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    window_ = glfwCreateWindow(width, height, title.c_str(), nullptr, nullptr);
    if (!window_) {
        std::cerr << "[Renderer] Failed to create GLFW window" << std::endl;
        glfwTerminate();
        return false;
    }
    glfwMakeContextCurrent(window_);
    glfwSetWindowUserPointer(window_, this);
    SetupCallbacks();
#else
    std::cout << "[Lumina-Renderer] Initializing " << width << "x" << height
              << " \"" << title << "\"" << std::endl;
#endif
    running_ = true;
    return true;
}

void Renderer::Run() {
#ifdef LUMINA_HAS_GLFW
    while (!glfwWindowShouldClose(window_) && running_) {
        glfwPollEvents();
        HandleInput();
        if (model_) {
            model_->Update(0.016f);
            model_->Render();
        }
        RenderFrame();
    }
#else
    std::cout << "[Lumina-Renderer] Entering main loop" << std::endl;
    while (running_) {
        HandleInput();
        if (model_) {
            model_->Update(0.016f);
            model_->Render();
        }
        RenderFrame();
    }
#endif
}

void Renderer::Shutdown() {
    running_ = false;
#ifdef LUMINA_HAS_GLFW
    if (window_) {
        glfwDestroyWindow(window_);
        window_ = nullptr;
    }
    glfwTerminate();
#endif
    std::cout << "[Lumina-Renderer] Shutdown" << std::endl;
}

void Renderer::SetupCallbacks() {
#ifdef LUMINA_HAS_GLFW
    glfwSetKeyCallback(window_, [](GLFWwindow*, int key, int scancode,
                                   int action, int mods) {
        auto* self = static_cast<Renderer*>(
            glfwGetWindowUserPointer(window_));
        if (self) self->HandleInput();
    });
#endif
}

void Renderer::RenderFrame() {
#ifdef LUMINA_HAS_GLFW
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glfwSwapBuffers(window_);
#endif
}

void Renderer::HandleInput() {
#ifdef LUMINA_HAS_GLFW
    // Input processed via GLFW callbacks registered in SetupCallbacks
#endif
}

} // namespace lumina
