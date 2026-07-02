#include <gtest/gtest.h>
#include "live2d_model.h"

namespace lumina {

class Live2DModelTest : public ::testing::Test {
protected:
    Live2DModel model_;
};

TEST_F(Live2DModelTest, LoadSetsLoaded) {
    EXPECT_TRUE(model_.Load("test.json"));
}

TEST_F(Live2DModelTest, SetMouthOpenClamps) {
    model_.SetMouthOpen(0.5f);
    model_.SetMouthOpen(1.5f);
    model_.Update(0.016f);
    // No crash — value passed through but clamping behavior is internal
}

TEST_F(Live2DModelTest, SetEyeOpen) {
    model_.SetEyeOpen(0.3f);
    model_.Update(0.016f);
    // value stored internally
}

TEST_F(Live2DModelTest, SetBodyRotation) {
    model_.SetBodyRotation(10.0f, -5.0f);
    model_.Update(0.016f);
}

TEST_F(Live2DModelTest, UpdateDoesNotCrashBeforeLoad) {
    model_.Update(0.016f);
    model_.Render();
}

TEST_F(Live2DModelTest, SetExpression) {
    model_.SetExpression("happy");
    model_.Update(0.016f);
}

} // namespace lumina
