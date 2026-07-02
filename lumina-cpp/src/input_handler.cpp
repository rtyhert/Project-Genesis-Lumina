#include "input_handler.h"
#include <iostream>
#include <algorithm>
#include <cstring>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#include <dshow.h>
#pragma comment(lib, "strmiids")

// qedit.h is deprecated in modern Windows SDKs; declare needed interfaces manually.
// ISampleGrabber interface (subset of qedit.h)
#ifndef __ISampleGrabber_INTERFACE_DEFINED__
#define __ISampleGrabber_INTERFACE_DEFINED__
DEFINE_GUID(CLSID_SampleGrabber, 0xc1f400a0, 0x3f08, 0x11d3, 0x9f, 0x0b,
            0x00, 0x60, 0x08, 0x03, 0x9e, 0x37);
DEFINE_GUID(IID_ISampleGrabber, 0x6b652fff, 0x11fe, 0x4fce, 0x92, 0xad,
            0x02, 0x66, 0xb5, 0xd7, 0xc7, 0x8f);

interface ISampleGrabberCB : public IUnknown {
    virtual STDMETHODIMP SampleCB(double SampleTime,
                                  IMediaSample *pSample) = 0;
    virtual STDMETHODIMP BufferCB(double SampleTime, BYTE *pBuffer,
                                  long BufferLen) = 0;
};

interface ISampleGrabber : public IUnknown {
    virtual STDMETHODIMP SetOneShot(BOOL OneShot) = 0;
    virtual STDMETHODIMP SetMediaType(const AM_MEDIA_TYPE *pType) = 0;
    virtual STDMETHODIMP GetConnectedMediaType(AM_MEDIA_TYPE *pType) = 0;
    virtual STDMETHODIMP SetBufferSamples(BOOL BufferTheSample) = 0;
    virtual STDMETHODIMP GetCurrentBuffer(long *pBufferSize,
                                          long *pBuffer) = 0;
    virtual STDMETHODIMP GetCurrentSample(IMediaSample **ppSample) = 0;
    virtual STDMETHODIMP SetCallback(ISampleGrabberCB *pCallback,
                                     long WhichMethodToCallback) = 0;
};
#endif // __ISampleGrabber_INTERFACE_DEFINED__
#endif // _WIN32

namespace lumina {

class InputHandler::Impl {
public:
    int camera_device_index_ = -1;
    bool camera_initialized_ = false;

#ifdef _WIN32
    // DirectShow capture graph
    IGraphBuilder* graph_ = nullptr;
    ICaptureGraphBuilder2* cap_builder_ = nullptr;
    IMediaControl* media_control_ = nullptr;
    ISampleGrabber* sample_grabber_ = nullptr;
    IBaseFilter* source_filter_ = nullptr;
    int frame_width_ = 640;
    int frame_height_ = 480;
    int frame_stride_ = 0;
#endif
};

bool KeyboardState::IsKeyDown(int key) const {
    auto it = keys.find(key);
    return it != keys.end() && it->second;
}

InputHandler::InputHandler()
    : impl_(std::make_unique<Impl>()) {}

InputHandler::~InputHandler() {
    ShutdownCamera();
}

void InputHandler::Update() {
    std::cout << "[InputHandler] Mouse: (" << mouse_.x << ", " << mouse_.y
              << ") L:" << (mouse_.left_down ? "1" : "0")
              << " R:" << (mouse_.right_down ? "1" : "0")
              << std::endl;
}

void InputHandler::SetKeyCallback(KeyCallback cb) {
    key_cb_ = std::move(cb);
}

void InputHandler::SetMouseButtonCallback(MouseButtonCallback cb) {
    mouse_btn_cb_ = std::move(cb);
}

void InputHandler::SetMouseMoveCallback(MouseMoveCallback cb) {
    mouse_move_cb_ = std::move(cb);
}

void InputHandler::SetScrollCallback(ScrollCallback cb) {
    scroll_cb_ = std::move(cb);
}

void InputHandler::SetCharCallback(CharCallback cb) {
    char_cb_ = std::move(cb);
}

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

bool InputHandler::IsClickOnModel(double mx, double my,
                                  float model_x, float model_y,
                                  float model_w, float model_h) const {
    return mx >= model_x && mx <= model_x + model_w &&
           my >= model_y && my <= model_y + model_h;
}

bool InputHandler::InitCamera(int device_index, int width, int height) {
#ifdef _WIN32
    ShutdownCamera();

    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) {
        std::cerr << "[InputHandler] CoInitializeEx failed" << std::endl;
        return false;
    }

    // Create capture graph builder
    hr = CoCreateInstance(CLSID_CaptureGraphBuilder2, nullptr,
                          CLSCTX_INPROC_SERVER,
                          IID_ICaptureGraphBuilder2,
                          reinterpret_cast<void**>(&impl_->cap_builder_));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to create CaptureGraphBuilder2"
                  << std::endl;
        return false;
    }

    // Create filter graph
    hr = CoCreateInstance(CLSID_FilterGraph, nullptr,
                          CLSCTX_INPROC_SERVER,
                          IID_IGraphBuilder,
                          reinterpret_cast<void**>(&impl_->graph_));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to create FilterGraph"
                  << std::endl;
        return false;
    }

    impl_->cap_builder_->SetFiltergraph(impl_->graph_);

    // Get IMediaControl
    hr = impl_->graph_->QueryInterface(IID_IMediaControl,
        reinterpret_cast<void**>(&impl_->media_control_));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to get IMediaControl"
                  << std::endl;
        return false;
    }

    // Create Sample Grabber
    hr = CoCreateInstance(CLSID_SampleGrabber, nullptr,
                          CLSCTX_INPROC_SERVER,
                          IID_ISampleGrabber,
                          reinterpret_cast<void**>(&impl_->sample_grabber_));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to create SampleGrabber"
                  << std::endl;
        return false;
    }

    // Configure grabber for RGB24
    AM_MEDIA_TYPE mt;
    ZeroMemory(&mt, sizeof(mt));
    mt.majortype = MEDIATYPE_Video;
    mt.subtype = MEDIASUBTYPE_RGB24;
    hr = impl_->sample_grabber_->SetMediaType(&mt);
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to set grabber media type"
                  << std::endl;
        return false;
    }

    // Enumerate video devices and find the requested index
    ICreateDevEnum* dev_enum = nullptr;
    hr = CoCreateInstance(CLSID_SystemDeviceEnum, nullptr,
                          CLSCTX_INPROC_SERVER,
                          IID_ICreateDevEnum,
                          reinterpret_cast<void**>(&dev_enum));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] No device enumerator" << std::endl;
        return false;
    }

    IEnumMoniker* enum_moniker = nullptr;
    hr = dev_enum->CreateClassEnumerator(CLSID_VideoInputDeviceCategory,
                                         &enum_moniker, 0);
    dev_enum->Release();
    if (FAILED(hr) || !enum_moniker) {
        std::cerr << "[InputHandler] No video devices" << std::endl;
        return false;
    }

    IMoniker* moniker = nullptr;
    ULONG fetched = 0;
    int idx = 0;
    bool found = false;
    while (enum_moniker->Next(1, &moniker, &fetched) == S_OK) {
        if (idx == device_index) {
            found = true;
            break;
        }
        moniker->Release();
        moniker = nullptr;
        ++idx;
    }
    enum_moniker->Release();

    if (!found || !moniker) {
        std::cerr << "[InputHandler] Camera " << device_index
                  << " not found" << std::endl;
        return false;
    }

    // Bind moniker to source filter
    hr = moniker->BindToObject(nullptr, nullptr, IID_IBaseFilter,
        reinterpret_cast<void**>(&impl_->source_filter_));
    moniker->Release();
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to bind camera device"
                  << std::endl;
        return false;
    }

    // Add source filter to graph
    hr = impl_->graph_->AddFilter(impl_->source_filter_, L"Video Capture");
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to add source filter to graph"
                  << std::endl;
        return false;
    }

    // Add Sample Grabber to graph
    IBaseFilter* grabber_base = nullptr;
    hr = impl_->sample_grabber_->QueryInterface(IID_IBaseFilter,
        reinterpret_cast<void**>(&grabber_base));
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to get grabber base filter"
                  << std::endl;
        return false;
    }
    hr = impl_->graph_->AddFilter(grabber_base, L"Sample Grabber");
    grabber_base->Release();
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to add grabber to graph"
                  << std::endl;
        return false;
    }

    // Render the capture stream (source → sample grabber → null renderer)
    hr = impl_->cap_builder_->RenderStream(
        &PIN_CATEGORY_CAPTURE, &MEDIATYPE_Video,
        impl_->source_filter_, grabber_base, nullptr);
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to render capture stream"
                  << std::endl;
        return false;
    }

    // Get the actual media type from the grabber connection
    AM_MEDIA_TYPE actual_mt;
    hr = impl_->sample_grabber_->GetConnectedMediaType(&actual_mt);
    if (SUCCEEDED(hr)) {
        VIDEOINFOHEADER* vih =
            reinterpret_cast<VIDEOINFOHEADER*>(actual_mt.pbFormat);
        if (vih) {
            impl_->frame_width_ = vih->bmiHeader.biWidth;
            impl_->frame_height_ = abs(vih->bmiHeader.biHeight);
            impl_->frame_stride_ = vih->bmiHeader.biSizeImage;
            if (impl_->frame_stride_ == 0) {
                impl_->frame_stride_ = impl_->frame_width_ *
                    impl_->frame_height_ * 3;
            }
        }
        CoTaskMemFree(actual_mt.pbFormat);
    }

    // Don't buffer samples — we'll grab the latest on demand
    hr = impl_->sample_grabber_->SetOneShot(FALSE);
    hr = impl_->sample_grabber_->SetBufferSamples(TRUE);

    // Run the graph
    hr = impl_->media_control_->Run();
    if (FAILED(hr)) {
        std::cerr << "[InputHandler] Failed to start capture graph"
                  << std::endl;
        return false;
    }

    impl_->camera_initialized_ = true;
    impl_->camera_device_index_ = device_index;
    impl_->frame_width_ = (width > 0) ? width : impl_->frame_width_;
    impl_->frame_height_ = (height > 0) ? height : impl_->frame_height_;
    std::cout << "[InputHandler] Camera initialized ("
              << impl_->frame_width_ << "x" << impl_->frame_height_
              << ")" << std::endl;
    return true;
#else
    (void)device_index;
    (void)width;
    (void)height;
    std::cerr << "[InputHandler] Camera not supported on this platform"
              << std::endl;
    return false;
#endif
}

bool InputHandler::CaptureCameraFrame(CameraFrame& frame) {
#ifdef _WIN32
    if (!impl_->camera_initialized_ || !impl_->sample_grabber_) {
        return false;
    }

    long buf_size = 0;
    HRESULT hr = impl_->sample_grabber_->GetCurrentBuffer(&buf_size, nullptr);
    if (FAILED(hr) || buf_size <= 0) {
        // No frame available yet
        frame.width = impl_->frame_width_;
        frame.height = impl_->frame_height_;
        frame.channels = 3;
        frame.data.resize(frame.width * frame.height * 3, 0);
        return true;
    }

    std::vector<BYTE> buffer(static_cast<size_t>(buf_size));
    hr = impl_->sample_grabber_->GetCurrentBuffer(&buf_size, buffer.data());
    if (FAILED(hr)) {
        return false;
    }

    frame.width = impl_->frame_width_;
    frame.height = impl_->frame_height_;
    frame.channels = 3;
    frame.data.assign(buffer.begin(), buffer.end());
    return true;
#else
    if (!impl_->camera_initialized_) return false;
    frame.width = 640;
    frame.height = 480;
    frame.channels = 3;
    frame.data.resize(frame.width * frame.height * frame.channels, 0);
    return true;
#endif
}

void InputHandler::ShutdownCamera() {
#ifdef _WIN32
    if (impl_->media_control_) {
        impl_->media_control_->Stop();
        impl_->media_control_->Release();
        impl_->media_control_ = nullptr;
    }
    if (impl_->sample_grabber_) {
        impl_->sample_grabber_->Release();
        impl_->sample_grabber_ = nullptr;
    }
    if (impl_->source_filter_) {
        impl_->graph_->RemoveFilter(impl_->source_filter_);
        impl_->source_filter_->Release();
        impl_->source_filter_ = nullptr;
    }
    if (impl_->cap_builder_) {
        impl_->cap_builder_->Release();
        impl_->cap_builder_ = nullptr;
    }
    if (impl_->graph_) {
        impl_->graph_->Release();
        impl_->graph_ = nullptr;
    }
#endif
    bool was_initialized = impl_->camera_initialized_;
    impl_->camera_initialized_ = false;
    impl_->camera_device_index_ = -1;
    if (was_initialized) {
        std::cout << "[InputHandler] Camera shut down" << std::endl;
    }
}

} // namespace lumina
