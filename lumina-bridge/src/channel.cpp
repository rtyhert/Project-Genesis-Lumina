#include "ipc_channel.h"
#include <iostream>
#include <cstring>

namespace lumina {

class IpcChannel::Impl {
public:
    std::string name;
    bool connected = false;
    MessageHandler handler;
};

IpcChannel::IpcChannel(const std::string& channel_name)
    : impl_(std::make_unique<Impl>()) {
    impl_->name = channel_name;
}

IpcChannel::~IpcChannel() {
    Shutdown();
}

bool IpcChannel::Initialize() {
    impl_->connected = true;
    std::cout << "[IpcChannel] Initialized: " << impl_->name << std::endl;
    return true;
}

void IpcChannel::Shutdown() {
    impl_->connected = false;
    impl_->handler = nullptr;
    std::cout << "[IpcChannel] Shutdown: " << impl_->name << std::endl;
}

bool IpcChannel::Send(const BridgeMessage& msg) {
    if (!impl_->connected) {
        std::cerr << "[IpcChannel] Cannot send on closed channel" << std::endl;
        return false;
    }
    if (impl_->handler) {
        impl_->handler(msg);
    }
    return true;
}

void IpcChannel::SetHandler(MessageHandler handler) {
    impl_->handler = std::move(handler);
}

bool IpcChannel::IsConnected() const {
    return impl_->connected;
}

} // namespace lumina
