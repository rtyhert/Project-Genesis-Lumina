#include <gtest/gtest.h>
#include "lip_sync_handler.h"

namespace lumina {

class MockLive2D : public Live2DModel {
public:
    float mouth_open_ = 0.0f;
    void SetMouthOpen(float v) override { mouth_open_ = v; }
    bool Load(const std::string&) override { return true; }
    void Update(float) override {}
    void Render() override {}
    void SetExpression(const std::string&) override {}
    void SetEyeOpen(float) override {}
    void SetBodyRotation(float, float) override {}
};

class LipSyncTest : public ::testing::Test {
protected:
    MockLive2D model_;
    LipSyncHandler handler_{&model_};
};

TEST_F(LipSyncTest, InitiallyIdle) {
    EXPECT_EQ(handler_.GetState(), LipSyncState::Idle);
    EXPECT_FALSE(handler_.IsPlaying());
    EXPECT_DOUBLE_EQ(handler_.GetCurrentTime(), 0.0);
}

TEST_F(LipSyncTest, PlayTransitionsToPlaying) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {1.0, 1.0}};
    data.total_duration = 1.0;
    handler_.LoadFrames(data);
    handler_.Play();
    EXPECT_EQ(handler_.GetState(), LipSyncState::Playing);
    EXPECT_TRUE(handler_.IsPlaying());
}

TEST_F(LipSyncTest, PauseResume) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {2.0, 1.0}};
    data.total_duration = 2.0;
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Pause();
    EXPECT_EQ(handler_.GetState(), LipSyncState::Paused);
    handler_.Play();
    EXPECT_EQ(handler_.GetState(), LipSyncState::Playing);
}

TEST_F(LipSyncTest, StopResetsState) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {1.0, 1.0}};
    data.total_duration = 1.0;
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Stop();
    EXPECT_EQ(handler_.GetState(), LipSyncState::Idle);
    EXPECT_DOUBLE_EQ(handler_.GetCurrentTime(), 0.0);
}

TEST_F(LipSyncTest, UpdateAdvancesTime) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {2.0, 1.0}};
    data.total_duration = 2.0;
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Update(0.5);
    EXPECT_GT(handler_.GetCurrentTime(), 0.0);
}

TEST_F(LipSyncTest, UpdateSetsMouthOpen) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {1.0, 1.0}};
    data.total_duration = 1.0;
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Update(1.0);
    EXPECT_GT(model_.mouth_open_, 0.0f);
}

TEST_F(LipSyncTest, FinishedAfterDuration) {
    LipSyncData data;
    data.frames = {{0.0, 0.0}, {1.0, 0.5}};
    data.total_duration = 1.0;
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Update(2.0);
    EXPECT_EQ(handler_.GetState(), LipSyncState::Finished);
}

TEST_F(LipSyncTest, InterpolateAtExactKeyframe) {
    std::vector<LipFrame> frames = {{0.0, 0.0}, {1.0, 1.0}, {2.0, 0.0}};
    LipFrame result = handler_.InterpolateFrame(0.0);
    EXPECT_DOUBLE_EQ(result.mouth_open, 0.0);
    result = handler_.InterpolateFrame(1.0);
    EXPECT_DOUBLE_EQ(result.mouth_open, 1.0);
}

TEST_F(LipSyncTest, InterpolateBetweenKeyframes) {
    std::vector<LipFrame> frames = {{0.0, 0.0}, {2.0, 1.0}};
    LipFrame result = handler_.InterpolateFrame(1.0);
    EXPECT_GT(result.mouth_open, 0.0);
    EXPECT_LT(result.mouth_open, 1.0);
}

TEST_F(LipSyncTest, EmptyFramesDoesNotCrash) {
    LipSyncData data;
    data.frames = {};
    handler_.LoadFrames(data);
    handler_.Play();
    handler_.Update(1.0);
    EXPECT_EQ(handler_.GetState(), LipSyncState::Playing);
}

} // namespace lumina
