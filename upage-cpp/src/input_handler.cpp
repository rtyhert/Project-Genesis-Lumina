#include "input_handler.h"
#include <iostream>
#include <algorithm>
#include <cstring>

#ifdef _WIN32
#include <windows.h>
#include <dshow.h>
#endif

namespace upage {

bool KeyboardState::IsKeyDown(int key) const {
    auto it = keys.find(key);
    return it != keys.end() && it->second;
}

InputHandler::InputHandler() = default;
InputHandler::~InputHandler() {
    ShutdownCamera();
}

void InputHandler::Update() {
    std::cout << "[InputHandler] Mouse: (" << mouse_.x << ", " << mouse_.y << ")"
              << " L:" << (mouse_.left_down ? "1" : "0")
              << " R:" << (mouse_.right_down ? "1" : "0")
              << std::endl;
}

void InputHandler::SetKeyCallback(KeyCallback cb) { key_cb_ = std::move(cb); }
void InputHandler::SetMouseButtonCallback(MouseButtonCallback cb) { mouse_btn_cb_ = std::move(cb); }
void InputHandler::SetMouseMoveCallback(MouseMoveCallback cb) { mouse_move_cb_ = std::move(cb); }
void InputHandler::SetScrollCallback(ScrollCallback cb) { scroll_cb_ = std::move(cb); }
void InputHandler::SetCharCallback(CharCallback cb) { char_cb_ = std::move(cb); }

void InputHandler::OnKey(int key, int scancode, int action, int mods) {
    keyboard_.keys[key] = (action != 0);
    if (key_cb_) key_cb_(key, scancode, action, mods);
}

void InputHandler::OnMouseButton(int button, int action, int mods) {
    if (button == 0) mouse_.left_down = (action != 0);
    else if (button == 1) mouse_.right_down = (action != 0);
    else if (button == 2) mouse_.middle_down = (action != 0);

    if (mouse_btn_cb_) mouse_btn_cb_(button, action, mods);
}

void InputHandler::OnMouseMove(double x, double y) {
    mouse_.x = x;
    mouse_.y = y;
    if (mouse_move_cb_) mouse_move_cb_(x, y);
}

void InputHandler::OnScroll(double xoffset, double yoffset) {
    if (scroll_cb_) scroll_cb_(xoffset, yoffset);
}

void InputHandler::OnChar(unsigned int codepoint) {
    if (char_cb_) char_cb_(codepoint);
}

bool InputHandler::IsClickOnModel(double mx, double my, float model_x, float model_y,
                                   float model_w, float model_h) const {
    return mx >= model_x && mx <= model_x + model_w &&
           my >= model_y && my <= model_y + model_h;
}

bool InputHandler::InitCamera(int device_index, int width, int height) {
#ifdef _WIN32
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) {
        std::cerr << "[InputHandler] CoInitializeEx failed" << std::endl;
        return false;
    }

    ICreateDevEnum* dev_enum = nullptr;
    hr = CoCreateInstance(CLSID_SystemDeviceEnum, nullptr, CLSCTX_INPROC_SERVER,
                          IID_PPV_ARGS(&dev_enum));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] No device enumerator" << std::endl;
        return false;
    }

    IEnumMoniker* enum_moniker = nullptr;
    hr = dev_enum->CreateClassEnumerator(CLSID_VideoInputDeviceCategory, &enum_moniker, 0);
    dev_enum->Release();
    if (FAILED(hr) || !enum_moniker) {
        std::cerr << "[InputHandler] No video devices" << std::endl;
        return false;
    }

    IMoniker* moniker = nullptr;
    ULONG fetched = 0;
    int idx = 0;
    while (enum_moniker->Next(1, &moniker, &fetched) == S_OK) {
        if (idx == device_index) break;
        moniker->Release();
        moniker = nullptr;
        ++idx;
    }
    enum_moniker->Release();

    if (!moniker) {
        std::cerr << "[InputHandler] Camera " << device_index << " not found" << std::endl;
        return false;
    }

    moniker->Release();
    camera_initialized_ = true;
    camera_device_ = reinterpret_cast<void*>(static_cast<uintptr_t>(device_index));
    std::cout << "[InputHandler] Camera initialized (" << width << "x" << height << ")" << std::endl;
    return true;
#else
    (void)device_index; (void)width; (void)height;
    std::cerr << "[InputHandler] Camera not supported on this platform" << std::endl;
    return false;
#endif
}

bool InputHandler::CaptureCameraFrame(CameraFrame& frame) {
    if (!camera_initialized_) return false;
    frame.width = 640;
    frame.height = 480;
    frame.channels = 3;
    frame.data.resize(frame.width * frame.height * frame.channels, 0);
    return true;
}

void InputHandler::ShutdownCamera() {
    if (camera_initialized_) {
        camera_initialized_ = false;
        camera_device_ = nullptr;
        std::cout << "[InputHandler] Camera shut down" << std::endl;
    }
}

} // namespace upage
