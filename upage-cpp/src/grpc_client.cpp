#include "bridge_client.h"
#include <iostream>

namespace upage {

BridgeClient::BridgeClient(const std::string& server_addr) {
    auto channel = grpc::CreateChannel(server_addr, grpc::InsecureChannelCredentials());
    stub_ = VirtualHuman::NewStub(channel);
    std::cout << "[Bridge] Connected to " << server_addr << std::endl;
}

BridgeClient::~BridgeClient() = default;

ChatOutput BridgeClient::ProcessChat(const ChatInput& input) {
    ChatRequest req;
    req.set_user_id(input.user_id);
    req.set_message(input.message);
    req.set_session_id(input.session_id);

    ChatResponse resp;
    grpc::ClientContext ctx;
    grpc::Status status = stub_->ProcessChat(&ctx, req, &resp);

    ChatOutput out;
    if (status.ok()) {
        out.reply_text = resp.reply_text();
        out.emotion = resp.emotion_tag();
        out.action = resp.action_tag();
    } else {
        out.reply_text = "[Error] " + status.error_message();
    }
    return out;
}

void BridgeClient::StreamAudio(const std::string& text, AudioCallback on_audio) {
    AudioRequest req;
    req.set_text(text);

    grpc::ClientContext ctx;
    std::unique_ptr<grpc::ClientReader<AudioChunk>> reader(
        stub_->StreamAudio(&ctx, req));

    AudioChunk chunk;
    while (reader->Read(&chunk)) {
        std::vector<float> samples(chunk.data().size() / sizeof(float));
        std::memcpy(samples.data(), chunk.data().data(), chunk.data().size());
        on_audio(samples);
    }
    reader->Finish();
}

bool BridgeClient::TriggerAction(const std::string& type, const std::string& emotion) {
    ActionRequest req;
    req.set_action_type(type);
    req.set_emotion(emotion);

    ActionResponse resp;
    grpc::ClientContext ctx;
    grpc::Status status = stub_->TriggerAction(&ctx, req, &resp);
    return status.ok() && resp.success();
}

} // namespace upage
