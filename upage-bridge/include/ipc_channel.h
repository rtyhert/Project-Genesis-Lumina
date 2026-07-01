#pragma once
#include <string>
#include <memory>
#include <functional>
#include <any>
#include <vector>

namespace upage {
namespace bridge {

enum class MessageType {
    CHAT_REQUEST,
    CHAT_RESPONSE,
    AUDIO_STREAM,
    LIP_SYNC,
    ACTION_TRIGGER,
    STATUS_EVENT,
};

struct Message {
    MessageType type;
    std::string payload;
    std::string topic;
    uint64_t timestamp;
};

class MessageQueue {
public:
    virtual ~MessageQueue() = default;
    virtual void Push(const Message& msg) = 0;
    virtual bool Pop(Message& msg) = 0;
    virtual size_t Size() const = 0;
};

class IPCChannel {
public:
    IPCChannel() = default;
    virtual ~IPCChannel() = default;
    virtual bool Connect(const std::string& endpoint) = 0;
    virtual void Disconnect() = 0;
    virtual bool Send(const Message& msg) = 0;
    virtual bool Receive(Message& msg) = 0;
    virtual bool IsConnected() const = 0;

    using ReceiveCallback = std::function<void(const Message&)>;
    void SetCallback(ReceiveCallback cb) { callback_ = cb; }

protected:
    ReceiveCallback callback_;
};

} // namespace bridge
} // namespace upage
