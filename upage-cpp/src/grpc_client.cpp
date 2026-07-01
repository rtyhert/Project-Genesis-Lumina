#include "bridge_client.h"
#include <iostream>
#include <chrono>
#include <thread>

namespace upage {

using grpc::Status;
using grpc::ClientContext;
using grpc::ClientReader;
using grpc::ClientAsyncResponseReader;
using grpc::CompletionQueue;

BridgeClient::BridgeClient(const std::string& server_addr)
    : addr_(server_addr), running_(false), reconnect_delay_ms_(1000) {
    CreateStub();
    running_ = true;
    worker_ = std::thread(&BridgeClient::AsyncCompletionLoop, this);
    std::cout << "[Bridge] Connected to " << server_addr << std::endl;
}

BridgeClient::~BridgeClient() {
    running_ = false;
    cq_.Shutdown();
    if (worker_.joinable()) worker_.join();
}

void BridgeClient::CreateStub() {
    auto channel = grpc::CreateChannel(addr_, grpc::InsecureChannelCredentials());
    stub_ = VirtualHuman::NewStub(channel);
    channel_ = channel;
}

bool BridgeClient::EnsureConnection() {
    if (channel_ && channel_->GetState(true) == GRPC_CHANNEL_READY) {
        reconnect_delay_ms_ = 1000;
        return true;
    }
    std::cerr << "[Bridge] Connection lost, reconnecting in "
              << reconnect_delay_ms_ << "ms ..." << std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(reconnect_delay_ms_));
    reconnect_delay_ms_ = std::min(reconnect_delay_ms_ * 2, 30000u);
    CreateStub();
    return channel_->GetState(true) != GRPC_CHANNEL_SHUTDOWN;
}

// ============== ProcessChat ==============

ChatOutput BridgeClient::ProcessChat(const ChatInput& input) {
    ChatResponse resp;
    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(30));

    ChatOutput out;
    for (int retry = 0; retry < 3; ++retry) {
        if (!EnsureConnection()) continue;

        ChatRequest req;
        req.set_user_id(input.user_id);
        req.set_message(input.message);
        req.set_session_id(input.session_id);
        for (const auto& [k, v] : input.context) {
            (*req.mutable_context())[k] = v;
        }

        Status status = stub_->ProcessChat(&ctx, req, &resp);
        if (status.ok()) {
            out.reply_text = resp.reply_text();
            out.emotion = resp.emotion_tag().category();
            out.action = resp.action_tag();
            return out;
        }
        if (status.error_code() == grpc::StatusCode::DEADLINE_EXCEEDED) {
            std::cerr << "[Bridge] ProcessChat timeout" << std::endl;
        } else {
            std::cerr << "[Bridge] ProcessChat error: "
                      << status.error_message() << std::endl;
            break;
        }
    }
    out.reply_text = "[Error] Failed to process chat";
    return out;
}

// ============== StreamAudio (async) ==============

void BridgeClient::StreamAudio(const std::string& text, AudioCallback on_audio) {
    if (!EnsureConnection()) return;

    AudioRequest req;
    req.set_text(text);

    auto ctx = std::make_shared<grpc::ClientContext>();
    ctx->set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(120));

    auto reader = stub_->StreamAudio(ctx.get(), req);
    AudioChunk chunk;

    while (reader->Read(&chunk)) {
        if (chunk.is_final()) break;
        std::vector<float> samples(chunk.data().size() / sizeof(float));
        if (!chunk.data().empty()) {
            std::memcpy(samples.data(), chunk.data().data(), chunk.data().size());
        }
        on_audio(samples);
    }

    Status status = reader->Finish();
    if (!status.ok()) {
        std::cerr << "[Bridge] StreamAudio error: "
                  << status.error_message() << std::endl;
    }
}

// ============== TriggerAction ==============

bool BridgeClient::TriggerAction(const std::string& type, const std::string& emotion, float intensity) {
    if (!EnsureConnection()) return false;

    ActionResponse resp;
    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(10));

    ActionRequest req;
    req.set_action_type(type);
    req.set_emotion(emotion);
    req.set_intensity(intensity);

    Status status = stub_->TriggerAction(&ctx, req, &resp);
    if (status.ok() && resp.success()) {
        std::cout << "[Bridge] Action triggered: " << resp.animation_id()
                  << " (" << resp.duration() << "s)" << std::endl;
        return true;
    }
    std::cerr << "[Bridge] TriggerAction failed: "
              << (status.ok() ? resp.error_message() : status.error_message())
              << std::endl;
    return false;
}

// ============== SendEmotion ==============

bool BridgeClient::SendEmotion(const std::string& session_id,
                                const std::string& category,
                                float intensity,
                                float valence,
                                float arousal) {
    if (!EnsureConnection()) return false;

    EmotionResponse resp;
    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(10));

    EmotionRequest req;
    req.set_session_id(session_id);
    req.mutable_emotion()->set_category(
        static_cast<EmotionCategory>(std::stoi(category)));
    req.mutable_emotion()->set_intensity(intensity);
    req.mutable_emotion()->set_valence(valence);
    req.mutable_emotion()->set_arousal(arousal);

    Status status = stub_->SendEmotion(&ctx, req, &resp);
    if (status.ok() && resp.success()) {
        std::cout << "[Bridge] Emotion sent: " << resp.transition_animation() << std::endl;
        return true;
    }
    std::cerr << "[Bridge] SendEmotion failed: "
              << status.error_message() << std::endl;
    return false;
}

// ============== Live2DControl ==============

bool BridgeClient::Live2DControl(const Live2DControlArgs& args) {
    if (!EnsureConnection()) return false;

    Live2DResponse resp;
    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(10));

    Live2DCommand cmd;
    cmd.set_session_id(args.session_id);
    cmd.set_transition_time(args.transition_time);
    cmd.set_queue(args.queue);
    cmd.set_priority(args.priority);

    switch (args.command_type) {
    case Live2DCommandType::kExpression: {
        auto* ctrl = cmd.mutable_expression();
        ctrl->set_type(static_cast<ExpressionType>(args.expression_type));
        ctrl->set_intensity(args.intensity);
        ctrl->set_duration(args.duration);
        break;
    }
    case Live2DCommandType::kMotion: {
        auto* ctrl = cmd.mutable_motion();
        ctrl->set_group(static_cast<MotionGroup>(args.motion_group));
        ctrl->set_animation_id(args.animation_id);
        ctrl->set_speed(args.speed);
        ctrl->set_loop(args.loop);
        break;
    }
    case Live2DCommandType::kParam: {
        auto* ctrl = cmd.mutable_param();
        ctrl->set_param_name(args.param_name);
        ctrl->set_value(args.param_value);
        break;
    }
    case Live2DCommandType::kLipSync: {
        auto* ctrl = cmd.mutable_lip_sync();
        ctrl->set_enabled(args.lip_sync_enabled);
        ctrl->set_gain(args.lip_sync_gain);
        break;
    }
    case Live2DCommandType::kPhysics: {
        auto* ctrl = cmd.mutable_physics();
        ctrl->set_enabled(args.physics_enabled);
        ctrl->set_reset(args.physics_reset);
        break;
    }
    }

    Status status = stub_->Live2DControl(&ctx, cmd, &resp);
    if (status.ok() && resp.success()) {
        std::cout << "[Bridge] Live2D: " << resp.animation_id()
                  << " (" << resp.transition_duration() << "s)" << std::endl;
        return true;
    }
    std::cerr << "[Bridge] Live2DControl failed: "
              << (status.ok() ? resp.error() : status.error_message())
              << std::endl;
    return false;
}

// ============== Stream Status (async) ==============

void BridgeClient::StreamStatus(const std::string& client_id,
                                 const std::vector<std::string>& events,
                                 StatusCallback on_event) {
    if (!EnsureConnection()) return;

    auto ctx = std::make_shared<grpc::ClientContext>();
    StatusRequest req;
    req.set_client_id(client_id);
    for (const auto& ev : events) {
        req.add_subscribed_events(ev);
    }

    auto reader = stub_->StreamStatus(ctx.get(), req);
    StatusEvent event;

    while (reader->Read(&event)) {
        on_event(event.event_type(), event.payload(), event.timestamp());
    }

    Status status = reader->Finish();
    if (!status.ok()) {
        std::cerr << "[Bridge] StreamStatus ended: "
                  << status.error_message() << std::endl;
    }
}

// ============== SendGift ==============

bool BridgeClient::SendGift(const std::string& stream_id,
                             const std::string& user_name,
                             const std::string& gift_name,
                             int count) {
    if (!EnsureConnection()) return false;

    GiftResponse resp;
    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(10));

    GiftNotify req;
    req.set_stream_id(stream_id);
    req.set_user_name(user_name);
    req.set_gift_name(gift_name);
    req.set_count(count);

    Status status = stub_->SendGift(&ctx, req, &resp);
    if (status.ok() && resp.success()) {
        std::cout << "[Bridge] Gift response: " << resp.thank_you_text() << std::endl;
        return true;
    }
    std::cerr << "[Bridge] SendGift failed: "
              << status.error_message() << std::endl;
    return false;
}

// ============== Async Completion Loop ==============

void BridgeClient::AsyncCompletionLoop() {
    void* tag;
    bool ok;
    while (running_) {
        auto deadline = std::chrono::system_clock::now() + std::chrono::milliseconds(100);
        auto status = cq_.AsyncNext(&tag, &ok, deadline);
        if (status == CompletionQueue::GOT_EVENT && tag) {
            auto* call = static_cast<AsyncCall*>(tag);
            if (call) call->Proceed(ok);
        }
    }
}

// ============== StreamLiveStatus (async reader) ==============

void BridgeClient::StreamLiveStatus(const std::string& stream_id,
                                     const std::string& platform,
                                     LiveStatusCallback on_event) {
    if (!EnsureConnection()) return;

    auto ctx = std::make_shared<grpc::ClientContext>();
    LiveStatusRequest req;
    req.set_stream_id(stream_id);
    req.set_platform(platform);

    auto reader = stub_->StreamLiveStatus(ctx.get(), req);
    LiveStatusEvent event;

    while (reader->Read(&event)) {
        LiveStatusData data;
        data.stream_id = event.stream_id();
        data.event_type = static_cast<int>(event.event_type());
        data.timestamp = event.timestamp();
        data.event_id = event.event_id();

        switch (event.event_data_case()) {
        case LiveStatusEvent::kAudienceMsg:
            data.user_name = event.audience_msg().user_name();
            data.message = event.audience_msg().message();
            break;
        case LiveStatusEvent::kGift:
            data.user_name = event.gift().user_name();
            data.message = event.gift().gift_name() + " x" +
                           std::to_string(event.gift().count());
            break;
        default:
            break;
        }
        on_event(data);
    }

    Status status = reader->Finish();
    if (!status.ok()) {
        std::cerr << "[Bridge] StreamLiveStatus ended: "
                  << status.error_message() << std::endl;
    }
}

} // namespace upage
