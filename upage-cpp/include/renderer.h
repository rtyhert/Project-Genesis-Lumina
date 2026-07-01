#pragma once
#include <string>
#include <memory>

namespace upage {

class Model2D {
public:
    virtual ~Model2D() = default;
    virtual bool Load(const std::string& path) = 0;
    virtual void Update(float dt) = 0;
    virtual void Render() = 0;
    virtual void SetExpression(const std::string& name) = 0;
    virtual void SetMouthOpen(float value) = 0;
    virtual void SetEyeOpen(float value) = 0;
    virtual void SetBodyRotation(float x, float y) = 0;
};

class Renderer {
public:
    Renderer();
    ~Renderer();

    bool Init(int width, int height, const std::string& title);
    void Run();
    void Shutdown();

    Model2D* GetModel() const { return model_.get(); }

private:
    void SetupCallbacks();
    void RenderFrame();
    void HandleInput();

    std::unique_ptr<Model2D> model_;
    bool running_ = false;
};

} // namespace upage
