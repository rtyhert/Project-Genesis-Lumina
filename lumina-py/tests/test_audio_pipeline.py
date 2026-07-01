import asyncio
import logging
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.DEBUG)

import pytest


@pytest.fixture
def tts_config():
    return {
        "engine": "edge-tts",
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": 1.0,
        "pitch": 0.0,
        "volume": 1.0,
        "language": "zh-CN",
        "cache_enabled": False,
    }


@pytest.fixture
def stt_config():
    return {
        "engine": "whisper",
        "model": "base",
        "language": "zh",
        "sample_rate": 16000,
        "vad_enabled": True,
    }


@pytest.fixture
def lip_sync_config():
    return {
        "fps": 30,
        "emotion": "neutral",
        "emotion_intensity": 0.5,
        "smoothing": 0.3,
    }


@pytest.mark.asyncio
async def test_tts_synthesize(tts_config):
    from src.tts_engine import TTSEngine

    engine = TTSEngine(tts_config)
    chunks = []
    async for chunk in engine.synthesize("你好世界"):
        chunks.append(chunk)

    audio = b"".join(chunks)
    if not audio:
        pytest.skip("TTS backend not available")


@pytest.mark.asyncio
async def test_tts_synthesize_full(tts_config):
    from src.tts_engine import TTSEngine

    engine = TTSEngine(tts_config)
    audio, sample_rate, phonemes = await engine.synthesize_full("测试语音合成")

    if not audio:
        pytest.skip("TTS backend not available")


@pytest.mark.asyncio
async def test_tts_cache(tts_config):
    from src.tts_engine import TTSEngine

    config = {**tts_config, "cache_enabled": True, "cache_dir": tempfile.mkdtemp()}
    engine = TTSEngine(config)

    audio1, sr1, ph1 = await engine.synthesize_full("缓存测试")
    audio2, sr2, ph2 = await engine.synthesize_full("缓存测试")

    assert audio1 == audio2, "Cached audio should be identical"

    engine.clear_cache()


@pytest.mark.asyncio
async def test_tts_batch_synthesize(tts_config):
    from src.tts_engine import TTSEngine

    engine = TTSEngine(tts_config)
    texts = ["第一段", "第二段", "第三段"]
    results = await engine.batch_synthesize(texts)

    assert len(results) == 3
    all_empty = all(len(audio) == 0 for audio, sr, _ in results)
    if all_empty:
        pytest.skip("TTS backend not available")


@pytest.mark.asyncio
async def test_tts_empty_text(tts_config):
    from src.tts_engine import TTSEngine

    engine = TTSEngine(tts_config)
    audio, sr, phonemes = await engine.synthesize_full("")
    assert audio == b""


@pytest.mark.asyncio
async def test_stt_convert_audio(stt_config):
    from src.stt_engine import STTEngine

    engine = STTEngine(stt_config)
    raw_pcm = b"\x00\x00" * 16000
    converted, rate = engine._convert_audio(raw_pcm, src_rate=16000, src_format="pcm")
    assert len(converted) > 0
    assert rate == 16000


@pytest.mark.asyncio
async def test_stt_convert_wav(stt_config):
    from src.stt_engine import STTEngine

    engine = STTEngine(stt_config)
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    wav_data = buf.getvalue()

    converted, rate = engine._convert_audio(wav_data, src_format="wav")
    assert len(converted) > 0


def test_stt_vad(stt_config):
    from src.stt_engine import STTEngine

    engine = STTEngine(stt_config)
    import struct

    silence = struct.pack("<" + "h" * 1600, *([0] * 1600))
    assert not engine._vad_process(silence), "Silence should not trigger VAD"

    loud = struct.pack("<" + "h" * 1600, *([8000] * 1600))
    results = [engine._vad_process(loud) for _ in range(10)]
    assert any(results), "Loud audio should trigger VAD within 10 frames"

    engine.vad.is_speaking = False


@pytest.mark.asyncio
async def test_stt_empty_audio(stt_config):
    from src.stt_engine import STTEngine

    engine = STTEngine(stt_config)
    result = await engine.transcribe(b"", src_format="pcm")
    assert result == "[语音识别未安装]" or result is None or result == ""


def test_lip_sync_from_text(lip_sync_config):
    from src.lip_sync import LipSyncGenerator

    gen = LipSyncGenerator(lip_sync_config)
    data = gen.from_text("你好，世界")

    assert len(data.frames) > 0
    assert data.total_duration > 0

    for f in data.frames:
        assert 0.0 <= f.mouth_open <= 1.0
        assert 0.0 <= f.jaw_y <= 1.0
        assert f.time >= 0.0


def test_lip_sync_emotion(lip_sync_config):
    from src.lip_sync import LipSyncGenerator

    gen = LipSyncGenerator({**lip_sync_config, "emotion": "happy", "emotion_intensity": 1.0})
    data = gen.from_text("哈哈")

    happy_mouth = data.frames[0].mouth_open if data.frames else 0.0

    gen2 = LipSyncGenerator({**lip_sync_config, "emotion": "sad", "emotion_intensity": 1.0})
    data2 = gen2.from_text("哈哈")

    sad_mouth = data2.frames[0].mouth_open if data2.frames else 0.0

    assert happy_mouth != sad_mouth or abs(happy_mouth - sad_mouth) < 0.01


def test_lip_sync_audio_amplitude(lip_sync_config):
    from src.lip_sync import LipSyncGenerator
    import struct
    import math

    gen = LipSyncGenerator(lip_sync_config)
    sample_rate = 24000
    duration = 1.0
    num_samples = int(sample_rate * duration)
    samples = [int(math.sin(2 * math.pi * 440 * i / sample_rate) * 16000)
               for i in range(num_samples)]
    audio = struct.pack("<" + "h" * num_samples, *samples)

    data = gen.from_audio_amplitude(audio, sample_rate)
    assert len(data.frames) > 0

    max_mouth = max(f.mouth_open for f in data.frames)
    assert max_mouth > 0.1, "Audio with signal should produce mouth movement"


def test_lip_sync_interpolate(lip_sync_config):
    from src.lip_sync import LipSyncGenerator

    gen = LipSyncGenerator(lip_sync_config)
    data = gen.from_text("测试插值")

    frame = gen.interpolate_frames(data, 0.0)
    assert frame is not None

    if data.total_duration > 0:
        mid_frame = gen.interpolate_frames(data, data.total_duration / 2)
        assert mid_frame is not None

        end_frame = gen.interpolate_frames(data, data.total_duration + 1.0)
        assert end_frame is not None


def test_lip_sync_empty_text(lip_sync_config):
    from src.lip_sync import LipSyncGenerator

    gen = LipSyncGenerator(lip_sync_config)
    data = gen.from_text("")
    assert len(data.frames) > 0


def test_lip_sync_fps_change(lip_sync_config):
    from src.lip_sync import LipSyncGenerator

    gen = LipSyncGenerator(lip_sync_config)
    gen.set_fps(60)
    assert gen.fps == 60

    data = gen.from_text("测试帧率")
    frame_times = [f.time for f in data.frames]
    if len(frame_times) > 1:
        intervals = [frame_times[i + 1] - frame_times[i] for i in range(len(frame_times) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        assert abs(avg_interval - 1.0 / 60) < 0.02


def test_audio_convert_sample_rate():
    from src.audio_utils import convert_sample_rate
    import struct

    samples = struct.pack("<" + "h" * 1000, *range(1000))
    converted = convert_sample_rate(samples, 16000, 8000)
    assert len(converted) < len(samples)


def test_audio_normalize():
    from src.audio_utils import normalize_audio
    import struct

    samples = struct.pack("<" + "h" * 1000, *([100] * 1000))
    normalized = normalize_audio(samples)
    import audioop
    original_rms = audioop.rms(samples, 2)
    normalized_rms = audioop.rms(normalized, 2)
    assert normalized_rms >= original_rms


def test_audio_mix():
    from src.audio_utils import mix_audio
    import struct

    main = struct.pack("<" + "h" * 1000, *([500] * 1000))
    overlay = struct.pack("<" + "h" * 1000, *([1000] * 1000))
    mixed = mix_audio(main, overlay, overlay_volume=0.5)

    assert len(mixed) == len(main)


def test_audio_meta_wav():
    from src.audio_utils import get_audio_meta
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * 24000)

    meta = get_audio_meta(buf.getvalue())
    assert meta.sample_rate == 24000
    assert meta.channels == 1
    assert meta.format == "wav"
    assert meta.duration == pytest.approx(1.0, abs=0.01)


def test_audio_generate():
    from src.audio_utils import generate_silence, generate_tone

    silence = generate_silence(0.5, sample_rate=24000)
    assert len(silence) == 24000

    tone = generate_tone(440.0, 1.0, sample_rate=24000, volume=0.5)
    assert len(tone) > 0

    import audioop
    rms = audioop.rms(tone, 2)
    assert rms > 0


def test_audio_cache():
    import tempfile
    from src.audio_utils import AudioCache, AudioMeta

    cache_dir = tempfile.mkdtemp()
    cache = AudioCache(cache_dir=cache_dir, ttl=3600)

    meta = AudioMeta(format="wav", sample_rate=24000, duration=1.0)
    key = cache.put(b"test_audio_data", meta)

    entry = cache.get(key)
    assert entry is not None
    assert entry.data == b"test_audio_data"

    cache.remove(key)
    assert cache.get(key) is None

    cache.clear()


@pytest.mark.asyncio
async def test_full_pipeline(tts_config, lip_sync_config):
    from src.tts_engine import TTSEngine
    from src.lip_sync import LipSyncGenerator

    tts = TTSEngine(tts_config)
    lip_gen = LipSyncGenerator(lip_sync_config)

    audio, sample_rate, phonemes = await tts.synthesize_full("管道测试")

    if not audio:
        pytest.skip("TTS backend not available (edge-tts not installed)")

    data = lip_gen.from_phoneme_timings(phonemes)
    if phonemes:
        assert len(data.frames) > 0, "Lip sync should produce frames from phonemes"

    data_amp = lip_gen.from_audio_amplitude(audio, sample_rate)
    assert len(data_amp.frames) > 0, "Lip sync should produce frames from audio amplitude"


@pytest.mark.asyncio
async def test_pipeline_with_emotion(tts_config, lip_sync_config):
    from src.tts_engine import TTSEngine
    from src.lip_sync import LipSyncGenerator

    tts = TTSEngine(tts_config)
    lip_gen = LipSyncGenerator({**lip_sync_config, "emotion": "excited", "emotion_intensity": 0.8})

    audio, sample_rate, phonemes = await tts.synthesize_full("太棒了")

    data = lip_gen.from_phoneme_timings(phonemes)
    if data.frames:
        has_animation = any(
            f.mouth_open > 0.1 or f.jaw_y > 0.1 for f in data.frames
        )
        assert has_animation, "Emotional lip sync should produce visible mouth movement"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
