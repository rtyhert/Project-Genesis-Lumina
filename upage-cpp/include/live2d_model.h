#pragma once
#include "renderer.h"
#include <string>

namespace upage {

class Live2DModel : public Model2D {
public:
    Live2DModel();
    ~Live2DModel() override;

    bool Load(const std::string& path) override;
    void Update(float dt) override;
    void Render() override;
    void SetExpression(const std::string& name) override;
    void SetMouthOpen(float value) override;
    void SetEyeOpen(float value) override;
    void SetBodyRotation(float x, float y) override;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace upage
