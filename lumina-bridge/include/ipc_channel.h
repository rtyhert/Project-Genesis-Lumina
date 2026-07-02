#pragma once
#include <string>
#include <functional>
#include <memory>
#include <vector>

namespace lumina {

enum class BridgeMessageType {
    kChatRequest,
    kChatResponse,
    kAudioData,
    kLipSync,
    kEmotion,
    kAction,
    kLive2DCommand,
    kStatusEvent,
    kGiftNotify,
    kShutdown,
};

struct BridgeMessage {
    BridgeMessageType type;
    std::string topic;
    std::vector<uint8_t> payload;
    uint64_t timestamp = 0;
};

class IpcChannel {
public:
    using MessageHandler = std::function<void(const BridgeMessage&)>;

    explicit IpcChannel(const std::string& channel_name);
    ~IpcChannel();

    bool Initialize();
    void Shutdown();

    bool Send(const BridgeMessage& msg);
    void SetHandler(MessageHandler handler);

    bool IsConnected() const;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace lumina
