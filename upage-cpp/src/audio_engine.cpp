#include "audio_engine.h"
#include <iostream>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <queue>
#include <memory>

#include <AL/al.h>
#include <AL/alc.h>

namespace upage {

class AudioEngine::Impl {
public:
    ALCdevice* device_ = nullptr;
    ALCcontext* context_ = nullptr;
    ALuint source_ = 0;
    std::vector<ALuint> buffers_;
    std::queue<std::vector<float>> pending_streams_;
    float volume_ = 1.0f;
    bool playing_ = false;
    bool paused_ = false;

    std::thread capture_thread_;
    std::atomic<bool> capturing_{false};
    ALCdevice* capture_device_ = nullptr;
    AudioCaptureCallback capture_cb_;

    std::mutex mutex_;
    std::condition_variable cv_;
};

AudioEngine::AudioEngine() : impl_(std::make_unique<Impl>()) {}

AudioEngine::~AudioEngine() {
    StopCapture();
    Stop();
    if (impl_->context_) {
        alcMakeContextCurrent(nullptr);
        alcDestroyContext(impl_->context_);
    }
    if (impl_->device_) {
        alcCloseDevice(impl_->device_);
    }
}

bool AudioEngine::Init(int sample_rate, int channels) {
    impl_->device_ = alcOpenDevice(nullptr);
    if (!impl_->device_) {
        std::cerr << "[AudioEngine] Failed to open OpenAL device" << std::endl;
        return false;
    }

    impl_->context_ = alcCreateContext(impl_->device_, nullptr);
    if (!impl_->context_ || !alcMakeContextCurrent(impl_->context_)) {
        std::cerr << "[AudioEngine] Failed to create OpenAL context" << std::endl;
        alcCloseDevice(impl_->device_);
        impl_->device_ = nullptr;
        return false;
    }

    alGenSources(1, &impl_->source_);
    ALenum err = alGetError();
    if (err != AL_NO_ERROR) {
        std::cerr << "[AudioEngine] Failed to generate source: 0x" << std::hex << err << std::endl;
        alcDestroyContext(impl_->context_);
        impl_->context_ = nullptr;
        alcCloseDevice(impl_->device_);
        impl_->device_ = nullptr;
        return false;
    }

    alSourcef(impl_->source_, AL_GAIN, impl_->volume_);
    alSourcei(impl_->source_, AL_LOOPING, AL_FALSE);

    std::cout << "[AudioEngine] Initialized (sample_rate=" << sample_rate
              << ", channels=" << channels << ")" << std::endl;
    return true;
}

void AudioEngine::PlayStream(const std::vector<float>& samples, int sample_rate) {
    if (!impl_->source_) return;

    ALenum format = AL_FORMAT_MONO_FLOAT32;
    ALsizei freq = sample_rate;

    ALuint buf;
    alGenBuffers(1, &buf);
    alBufferData(buf, format, samples.data(),
                 static_cast<ALsizei>(samples.size() * sizeof(float)), freq);

    ALenum err = alGetError();
    if (err != AL_NO_ERROR) {
        std::cerr << "[AudioEngine] alBufferData error: 0x" << std::hex << err << std::endl;
        alDeleteBuffers(1, &buf);
        return;
    }

    alSourceQueueBuffers(impl_->source_, 1, &buf);

    ALint state;
    alGetSourcei(impl_->source_, AL_SOURCE_STATE, &state);
    if (state != AL_PLAYING) {
        alSourcePlay(impl_->source_);
    }

    impl_->playing_ = true;
    impl_->paused_ = false;
}

void AudioEngine::Stop() {
    if (!impl_->source_) return;

    alSourceStop(impl_->source_);

    ALint queued;
    alGetSourcei(impl_->source_, AL_BUFFERS_QUEUED, &queued);
    if (queued > 0) {
        ALuint buf;
        while (alSourceUnqueueBuffers(impl_->source_, 1, &buf) == AL_NO_ERROR) {
            alDeleteBuffers(1, &buf);
        }
    }

    impl_->playing_ = false;
    impl_->paused_ = false;
}

void AudioEngine::Pause() {
    if (!impl_->source_ || !impl_->playing_) return;
    alSourcePause(impl_->source_);
    impl_->paused_ = true;
}

void AudioEngine::Resume() {
    if (!impl_->source_ || !impl_->paused_) return;
    alSourcePlay(impl_->source_);
    impl_->paused_ = false;
}

void AudioEngine::SetVolume(float v) {
    impl_->volume_ = v;
    if (impl_->source_) {
        alSourcef(impl_->source_, AL_GAIN, v);
    }
}

bool AudioEngine::IsPlaying() const {
    if (!impl_->source_) return false;
    ALint state;
    alGetSourcei(impl_->source_, AL_SOURCE_STATE, &state);
    return state == AL_PLAYING;
}

float AudioEngine::GetCurrentTime() const {
    if (!impl_->source_) return 0.0f;
    ALfloat sec;
    alGetSourcef(impl_->source_, AL_SEC_OFFSET, &sec);
    return sec;
}

void AudioEngine::StartCapture(AudioCaptureCallback cb) {
    if (impl_->capturing_.load()) return;

    impl_->capture_cb_ = std::move(cb);
    impl_->capture_device_ = alcCaptureOpenDevice(nullptr, 16000, AL_FORMAT_MONO_FLOAT32, 16000);
    if (!impl_->capture_device_) {
        std::cerr << "[AudioEngine] Failed to open capture device" << std::endl;
        return;
    }

    alcCaptureStart(impl_->capture_device_);
    impl_->capturing_ = true;

    impl_->capture_thread_ = std::thread([this]() {
        const int samples_per_chunk = 1600; // 100ms at 16kHz
        while (impl_->capturing_.load()) {
            ALint avail;
            alcGetIntegerv(impl_->capture_device_, ALC_CAPTURE_SAMPLES, 1, &avail);
            if (avail >= samples_per_chunk) {
                std::vector<float> buf(samples_per_chunk);
                alcCaptureSamples(impl_->capture_device_, buf.data(), samples_per_chunk);
                if (impl_->capture_cb_) {
                    impl_->capture_cb_(buf);
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    });
}

void AudioEngine::StopCapture() {
    impl_->capturing_ = false;
    if (impl_->capture_thread_.joinable()) {
        impl_->capture_thread_.join();
    }
    if (impl_->capture_device_) {
        alcCaptureStop(impl_->capture_device_);
        alcCaptureCloseDevice(impl_->capture_device_);
        impl_->capture_device_ = nullptr;
    }
}

} // namespace upage
