#pragma once
#include <functional>
#include <memory>
#include <vector>

namespace lumina {

class AudioEngine {
public:
    AudioEngine();
    ~AudioEngine();
    bool Init(int sample_rate = 44100, int channels = 1);
    void PlayStream(const std::vector<float>& samples, int sample_rate);
    void Stop();
    void Pause();
    void Resume();
    float GetVolume() const;
    void SetVolume(float v);
    bool IsPlaying() const;
    float GetCurrentTime() const;

    using AudioCaptureCallback = std::function<void(const std::vector<float>&)>;
    void StartCapture(AudioCaptureCallback cb);
    void StopCapture();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace lumina
