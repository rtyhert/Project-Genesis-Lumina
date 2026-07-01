#pragma once
#include <functional>
#include <vector>

namespace upage {

class AudioEngine {
public:
    AudioEngine();
    ~AudioEngine();

    bool Init(int sample_rate = 44100, int channels = 1);
    void PlayStream(const std::vector<float>& samples, int sample_rate);
    void Stop();
    void Pause();
    void Resume();
    float GetVolume() const { return volume_; }
    void SetVolume(float v) { volume_ = v; }
    bool IsPlaying() const;
    float GetCurrentTime() const;

    using AudioCaptureCallback = std::function<void(const std::vector<float>&)>;
    void StartCapture(AudioCaptureCallback cb);
    void StopCapture();

private:
    float volume_ = 1.0f;
};

} // namespace upage
