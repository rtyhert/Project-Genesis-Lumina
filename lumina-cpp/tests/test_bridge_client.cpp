#pragma once
#include <gtest/gtest.h>
#include "bridge_client.h"

namespace lumina {

class BridgeClientTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Use a non-routable address to test connection handling
        client = std::make_unique<BridgeClient>("127.0.0.1:1");
    }

    void TearDown() override {
        client.reset();
    }

    std::unique_ptr<BridgeClient> client;
};

TEST_F(BridgeClientTest, IsConnectedInitiallyReturnsFalse) {
    EXPECT_FALSE(client->IsConnected());
}

TEST_F(BridgeClientTest, GetEndpoint) {
    EXPECT_EQ(client->GetEndpoint(), "127.0.0.1:1");
}

TEST_F(BridgeClientTest, ProcessChatReturnsEmptyOnConnectionFailure) {
    ChatInput input;
    input.user_id = "test_user";
    input.message = "hello";
    input.session_id = "session_1";

    ChatOutput output = client->ProcessChat(input);
    EXPECT_TRUE(output.reply_text == "[Error] Failed to process chat" || output.reply_text.empty());
}

TEST_F(BridgeClientTest, TriggerActionReturnsFalseOnConnectionFailure) {
    bool result = client->TriggerAction("wave", "happy", 1.0f);
    EXPECT_FALSE(result);
}

TEST_F(BridgeClientTest, SendEmotionReturnsFalseOnConnectionFailure) {
    bool result = client->SendEmotion("session_1", 0, 0.8f, 0.9f, 0.6f);
    EXPECT_FALSE(result);
}

TEST_F(BridgeClientTest, Live2DControlReturnsFalseOnConnectionFailure) {
    Live2DControlArgs args;
    args.session_id = "session_1";
    args.command_type = 0;
    bool result = client->Live2DControl(args);
    EXPECT_FALSE(result);
}

TEST_F(BridgeClientTest, SendGiftReturnsFalseOnConnectionFailure) {
    bool result = client->SendGift("stream_1", "ViewerA", "火箭", 1);
    EXPECT_FALSE(result);
}

TEST_F(BridgeClientTest, MultipleInstances) {
    BridgeClient c1("127.0.0.1:1");
    BridgeClient c2("127.0.0.1:2");
    BridgeClient c3("127.0.0.1:3");

    EXPECT_EQ(c1.GetEndpoint(), "127.0.0.1:1");
    EXPECT_EQ(c2.GetEndpoint(), "127.0.0.1:2");
    EXPECT_EQ(c3.GetEndpoint(), "127.0.0.1:3");
}

} // namespace lumina
