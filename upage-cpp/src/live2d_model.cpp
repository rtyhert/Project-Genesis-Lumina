#include "live2d_model.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <cstring>
#include <cmath>

namespace upage {

class Live2DModel::Impl {
public:
    std::string model_path_;
    float mouth_open_ = 0.0f;
    float eye_open_ = 1.0f;
    float body_rot_x_ = 0.0f;
    float body_rot_y_ = 0.0f;
    std::string current_expression_;
    bool loaded_ = false;

    struct Param {
        std::string id;
        float value;
        float min;
        float max;
        float default_value;
    };
    std::vector<Param> parameters_;

    struct PartOpacity {
        std::string id;
        float opacity;
    };
    std::vector<PartOpacity> parts_;
};

Live2DModel::Live2DModel() : impl_(std::make_unique<Impl>()) {}
Live2DModel::~Live2DModel() = default;

bool Live2DModel::Load(const std::string& path) {
    impl_->model_path_ = path;
    impl_->loaded_ = true;
    impl_->current_expression_ = "neutral";

    impl_->parameters_.clear();
    impl_->parameters_.push_back({"ParamAngleX", 0.0f, -30.0f, 30.0f, 0.0f});
    impl_->parameters_.push_back({"ParamAngleY", 0.0f, -30.0f, 30.0f, 0.0f});
    impl_->parameters_.push_back({"ParamMouthOpenY", 0.0f, 0.0f, 1.0f, 0.0f});
    impl_->parameters_.push_back({"ParamEyeLOpen", 1.0f, 0.0f, 1.0f, 1.0f});
    impl_->parameters_.push_back({"ParamEyeROpen", 1.0f, 0.0f, 1.0f, 1.0f});
    impl_->parameters_.push_back({"ParamBodyAngleX", 0.0f, -30.0f, 30.0f, 0.0f});
    impl_->parameters_.push_back({"ParamBodyAngleY", 0.0f, -30.0f, 30.0f, 0.0f});

    impl_->parts_.clear();
    impl_->parts_.push_back({"PartArmL", 1.0f});
    impl_->parts_.push_back({"PartArmR", 1.0f});

    std::cout << "[Live2DModel] Loaded model from " << path << std::endl;
    return true;
}

void Live2DModel::Update(float dt) {
    if (!impl_->loaded_) return;

    for (auto& p : impl_->parameters_) {
        if (p.id == "ParamMouthOpenY") {
            p.value = impl_->mouth_open_;
        } else if (p.id == "ParamEyeLOpen" || p.id == "ParamEyeROpen") {
            p.value = impl_->eye_open_;
        } else if (p.id == "ParamBodyAngleX") {
            p.value = impl_->body_rot_x_;
        } else if (p.id == "ParamBodyAngleY") {
            p.value = impl_->body_rot_y_;
        }
    }
}

void Live2DModel::Render() {
    if (!impl_->loaded_) return;

    // In a full implementation this would use Live2D Cubism SDK rendering:
    // csmUpdateModel(model_);
    // csmDrawModel(model_);

    std::cout << "[Live2DModel] Render frame - expr:" << impl_->current_expression_
              << " mouth:" << impl_->mouth_open_
              << " eye:" << impl_->eye_open_
              << std::endl;
}

void Live2DModel::SetExpression(const std::string& name) {
    impl_->current_expression_ = name;
    std::cout << "[Live2DModel] SetExpression: " << name << std::endl;
}

void Live2DModel::SetMouthOpen(float value) {
    impl_->mouth_open_ = std::clamp(value, 0.0f, 1.0f);
}

void Live2DModel::SetEyeOpen(float value) {
    impl_->eye_open_ = std::clamp(value, 0.0f, 1.0f);
}

void Live2DModel::SetBodyRotation(float x, float y) {
    impl_->body_rot_x_ = std::clamp(x, -30.0f, 30.0f);
    impl_->body_rot_y_ = std::clamp(y, -30.0f, 30.0f);
}

} // namespace upage
