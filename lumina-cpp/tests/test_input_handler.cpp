#include <gtest/gtest.h>
#include "input_handler.h"

namespace lumina {

class InputHandlerTest : public ::testing::Test {
protected:
    InputHandler handler_;
};

TEST_F(InputHandlerTest, MouseDefaults) {
    const auto& mouse = handler_.GetMouse();
    EXPECT_DOUBLE_EQ(mouse.x, 0.0);
    EXPECT_DOUBLE_EQ(mouse.y, 0.0);
    EXPECT_FALSE(mouse.left_down);
    EXPECT_FALSE(mouse.right_down);
    EXPECT_FALSE(mouse.middle_down);
}

TEST_F(InputHandlerTest, OnMouseMoveUpdatesPosition) {
    handler_.OnMouseMove(100.0, 200.0);
    const auto& mouse = handler_.GetMouse();
    EXPECT_DOUBLE_EQ(mouse.x, 100.0);
    EXPECT_DOUBLE_EQ(mouse.y, 200.0);
}

TEST_F(InputHandlerTest, OnMouseButtonTracksLeftButton) {
    handler_.OnMouseButton(0, 1, 0);
    EXPECT_TRUE(handler_.GetMouse().left_down);
    handler_.OnMouseButton(0, 0, 0);
    EXPECT_FALSE(handler_.GetMouse().left_down);
}

TEST_F(InputHandlerTest, OnMouseButtonTracksRightButton) {
    handler_.OnMouseButton(1, 1, 0);
    EXPECT_TRUE(handler_.GetMouse().right_down);
}

TEST_F(InputHandlerTest, OnMouseButtonTracksMiddleButton) {
    handler_.OnMouseButton(2, 1, 0);
    EXPECT_TRUE(handler_.GetMouse().middle_down);
}

TEST_F(InputHandlerTest, OnKeySetsKeyState) {
    handler_.OnKey(65, 0, 1, 0);  // 'A' pressed
    EXPECT_TRUE(handler_.GetKeyboard().IsKeyDown(65));
    handler_.OnKey(65, 0, 0, 0);  // 'A' released
    EXPECT_FALSE(handler_.GetKeyboard().IsKeyDown(65));
}

TEST_F(InputHandlerTest, IsClickOnModel) {
    EXPECT_TRUE(handler_.IsClickOnModel(50, 50, 0, 0, 100, 100));
    EXPECT_FALSE(handler_.IsClickOnModel(200, 200, 0, 0, 100, 100));
    EXPECT_FALSE(handler_.IsClickOnModel(-10, 50, 0, 0, 100, 100));
}

TEST_F(InputHandlerTest, CallbackFiresOnKey) {
    int last_key = -1;
    handler_.SetKeyCallback([&](int key, int, int, int) { last_key = key; });
    handler_.OnKey(32, 0, 1, 0);
    EXPECT_EQ(last_key, 32);
}

TEST_F(InputHandlerTest, CallbackFiresOnMouseMove) {
    double last_x = -1, last_y = -1;
    handler_.SetMouseMoveCallback([&](double x, double y) {
        last_x = x; last_y = y;
    });
    handler_.OnMouseMove(42.0, 99.0);
    EXPECT_DOUBLE_EQ(last_x, 42.0);
    EXPECT_DOUBLE_EQ(last_y, 99.0);
}

} // namespace lumina
