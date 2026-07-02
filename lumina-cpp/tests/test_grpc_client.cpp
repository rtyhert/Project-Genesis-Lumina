#include <gtest/gtest.h>
#include <grpcpp/grpcpp.h>
#include "lumina.pb.h"
#include "lumina.grpc.pb.h"

namespace lumina {

class GrpcStubTest : public ::testing::Test {
protected:
    void SetUp() override {
        channel = grpc::CreateChannel("localhost:50051",
                                      grpc::InsecureChannelCredentials());
        stub = VirtualHuman::NewStub(channel);
    }

    std::shared_ptr<grpc::Channel> channel;
    std::unique_ptr<VirtualHuman::Stub> stub;
};

TEST_F(GrpcStubTest, ChannelIsCreated) {
    ASSERT_NE(channel, nullptr);
    EXPECT_EQ(channel->GetTarget(), "localhost:50051");
}

TEST_F(GrpcStubTest, StubIsCreated) {
    ASSERT_NE(stub, nullptr);
}

TEST_F(GrpcStubTest, ChatRequestFields) {
    ChatRequest req;
    req.set_user_id("test_user");
    req.set_message("hello");
    req.set_session_id("session_1");

    EXPECT_EQ(req.user_id(), "test_user");
    EXPECT_EQ(req.message(), "hello");
    EXPECT_EQ(req.session_id(), "session_1");
}

TEST_F(GrpcStubTest, ChatRequestDefaultFields) {
    ChatRequest req;
    EXPECT_TRUE(req.user_id().empty());
    EXPECT_TRUE(req.message().empty());
    EXPECT_TRUE(req.session_id().empty());
}

TEST_F(GrpcStubTest, EmotionTagFields) {
    EmotionTag tag;
    tag.set_category(EmotionCategory::HAPPY);
    tag.set_intensity(0.8f);
    tag.set_valence(0.9f);
    tag.set_arousal(0.6f);

    EXPECT_EQ(tag.category(), EmotionCategory::HAPPY);
    EXPECT_FLOAT_EQ(tag.intensity(), 0.8f);
    EXPECT_FLOAT_EQ(tag.valence(), 0.9f);
    EXPECT_FLOAT_EQ(tag.arousal(), 0.6f);
}

TEST_F(GrpcStubTest, AudioChunkFields) {
    AudioChunk chunk;
    chunk.set_data(std::string(160, '\x00'));
    chunk.set_sequence(42);
    chunk.set_is_final(false);

    EXPECT_EQ(chunk.data().size(), 160);
    EXPECT_EQ(chunk.sequence(), 42);
    EXPECT_FALSE(chunk.is_final());
}

TEST_F(GrpcStubTest, Live2DControlArgs) {
    Live2DCommand req;
    req.set_session_id("session_1");
    req.set_transition_time(0.3f);
    req.set_queue(false);
    req.set_priority(1);

    EXPECT_EQ(req.session_id(), "session_1");
    EXPECT_FLOAT_EQ(req.transition_time(), 0.3f);
    EXPECT_FALSE(req.queue());
    EXPECT_EQ(req.priority(), 1);
}

TEST_F(GrpcStubTest, GiftRequestFields) {
    GiftNotify req;
    req.set_stream_id("stream_1");
    req.set_user_name("UserA");
    req.set_gift_name("火箭");
    req.set_count(10);

    EXPECT_EQ(req.stream_id(), "stream_1");
    EXPECT_EQ(req.user_name(), "UserA");
    EXPECT_EQ(req.gift_name(), "火箭");
    EXPECT_EQ(req.count(), 10);
}

} // namespace lumina
