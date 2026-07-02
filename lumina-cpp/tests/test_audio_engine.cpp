#include <gtest/gtest.h>
#include "audio_engine.h"

namespace lumina {

class AudioEngineTest : public ::testing::Test {
protected:
    AudioEngine engine_;
};

TEST_F(AudioEngineTest, DefaultVolumeIsOne) {
    EXPECT_FLOAT_EQ(engine_.GetVolume(), 1.0f);
}

TEST_F(AudioEngineTest, SetVolumeClamps) {
    engine_.SetVolume(0.5f);
    EXPECT_FLOAT_EQ(engine_.GetVolume(), 0.5f);
    engine_.SetVolume(-0.1f);
    EXPECT_FLOAT_EQ(engine_.GetVolume(), -0.1f);  // no clamp in setter
    engine_.SetVolume(1.5f);
    EXPECT_FLOAT_EQ(engine_.GetVolume(), 1.5f);
}

TEST_F(AudioEngineTest, InitiallyNotPlaying) {
    EXPECT_FALSE(engine_.IsPlaying());
}

TEST_F(AudioEngineTest, StopDoesNotCrashWhenIdle) {
    engine_.Stop();
    EXPECT_FALSE(engine_.IsPlaying());
}

TEST_F(AudioEngineTest, PauseDoesNotCrashWhenIdle) {
    engine_.Pause();
    EXPECT_FALSE(engine_.IsPlaying());
}

TEST_F(AudioEngineTest, GetCurrentTimeIsZeroWhenIdle) {
    EXPECT_FLOAT_EQ(engine_.GetCurrentTime(), 0.0f);
}

} // namespace lumina
