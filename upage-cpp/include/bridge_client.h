#pragma once
#include <string>
#include <memory>
#include <functional>
#include <grpcpp/grpcpp.h>
#include "upage.pb.h"
#include "upage.grpc.pb.h"

namespace upage {

struct ChatInput {
    std::string user_id;
    std::string message;
    std::string session_id;
};

struct ChatOutput {
    std::string reply_text;
    std::string emotion;
    std::string action;
};

using AudioCallback = std::function<void(const std::vector<float>& samples)>;

class BridgeClient {
public:
    explicit BridgeClient(const std::string& server_addr);
    ~BridgeClient();

    ChatOutput ProcessChat(const ChatInput& input);
    void StreamAudio(const std::string& text, AudioCallback on_audio);
    bool TriggerAction(const std::string& type, const std::string& emotion);

private:
    std::unique_ptr<VirtualHuman::Stub> stub_;
    grpc::CompletionQueue cq_;
};

} // namespace upage
