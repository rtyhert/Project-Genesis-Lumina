#include "ipc_channel.h"
#include <cstring>
#include <iostream>

namespace upage::bridge {

class GrpcChannel : public IPCChannel {
public:
    GrpcChannel() = default;
    ~GrpcChannel() override { Disconnect(); }

    bool Connect(const std::string& endpoint) override {
        endpoint_ = endpoint;
        std::cout << "[IPC] Connected to " << endpoint << std::endl;
        connected_ = true;
        return true;
    }

    void Disconnect() override {
        connected_ = false;
        std::cout << "[IPC] Disconnected" << std::endl;
    }

    bool Send(const Message& msg) override {
        if (!connected_) return false;
        std::cout << "[IPC] Sent: type=" << static_cast<int>(msg.type)
                  << " payload=" << msg.payload.size() << "B" << std::endl;
        return true;
    }

    bool Receive(Message& msg) override {
        if (!connected_) return false;
        return false;
    }

    bool IsConnected() const override { return connected_; }

private:
    std::string endpoint_;
    bool connected_ = false;
};

std::unique_ptr<IPCChannel> CreateChannel() {
    return std::make_unique<GrpcChannel>();
}

} // namespace upage::bridge
