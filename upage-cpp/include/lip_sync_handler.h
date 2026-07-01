#pragma once
#include <functional>
#include <memory>
#include <vector>
#include <string>
#include <cstdint>

namespace upage {

struct LipFrame {
    double time = 0.0;
    double mouth_open = 0.0;
    double jaw_y = 0.0;
    double tongue_x = 0.0;
    double tongue_y = 0.0;
    double lip_width = 0.5;
};

struct LipSyncData {
    std::vector<LipFrame> frames;
    double total_duration = 0.0;
};

enum class LipSyncState {
    Idle,
    Playing,
    Paused,
    Finished
};

class Live2DModel;

class LipSyncHandler {
public:
    explicit LipSyncHandler(Live2DModel* model = nullptr);
    ~LipSyncHandler();

    void SetLive2DModel(Live2DModel* model);

    void LoadFrames(const LipSyncData& data);
    void LoadFrames(const std::vector<LipFrame>& frames, double total_duration);

    void Update(double delta_time);

    bool IsPlaying() const;
    void Play();
    void Pause();
    void Stop();
    void Seek(double time);

    double GetCurrentTime() const { return current_time_; }
    double GetTotalDuration() const { return total_duration_; }
    LipSyncState GetState() const { return state_; }

    void SetInterpolationAlpha(double alpha) { interpolation_alpha_ = alpha; }
    double GetInterpolationAlpha() const { return interpolation_alpha_; }

    void SetGain(double gain) { gain_ = gain; }
    double GetGain() const { return gain_; }

    void SetAudioTimeSource(std::function<double()> time_source);
    void ClearAudioTimeSource();

    using FrameCallback = std::function<void(const LipFrame&)>;
    void SetFrameCallback(FrameCallback cb) { frame_cb_ = std::move(cb); }

    LipFrame GetCurrentFrame() const;
    LipFrame InterpolateFrame(double time) const;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;

    Live2DModel* model_ = nullptr;
    std::vector<LipFrame> frames_;
    double total_duration_ = 0.0;
    double current_time_ = 0.0;
    double interpolation_alpha_ = 0.3;
    double gain_ = 1.0;
    LipSyncState state_ = LipSyncState::Idle;

    std::function<double()> audio_time_source_;
    FrameCallback frame_cb_;
};

} // namespace upage
