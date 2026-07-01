import asyncio
import hashlib
import io
import json
import logging
import os
import struct
import tempfile
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lumina.audio_utils")


@dataclass
class AudioMeta:
    format: str = "wav"
    sample_rate: int = 24000
    channels: int = 1
    bits_per_sample: int = 16
    duration: float = 0.0

    @property
    def frame_size(self) -> int:
        return self.channels * (self.bits_per_sample // 8)


@dataclass
class CacheEntry:
    data: bytes
    meta: AudioMeta
    created_at: float = field(default_factory=time.time)


class AudioConverter:
    PCM_FORMATS = {"pcm", "raw"}
    WAV_FORMATS = {"wav"}
    MP3_FORMATS = {"mp3"}
    SUPPORTED_FORMATS = PCM_FORMATS | WAV_FORMATS | MP3_FORMATS

    @staticmethod
    def detect_format(data: bytes) -> str:
        if len(data) < 4:
            return "pcm"
        if data[:4] == b"RIFF":
            return "wav"
        if data[:3] == b"ID3":
            return "mp3"
        if len(data) > 2 and (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return "mp3"
        return "pcm"

    @staticmethod
    def to_wav(data: bytes, src_sample_rate: int = 24000, src_format: str = "pcm",
               channels: int = 1, bits: int = 16) -> bytes:
        detected = AudioConverter.detect_format(data)
        fmt = src_format if src_format != "auto" else detected

        if fmt == "wav":
            return data

        if fmt == "mp3":
            return AudioConverter._mp3_to_wav(data, src_sample_rate)

        raw = AudioConverter.to_pcm(data, src_sample_rate, fmt)
        return AudioConverter._raw_to_wav(raw, src_sample_rate, channels, bits)

    @staticmethod
    def to_pcm(data: bytes, src_sample_rate: int = 24000, src_format: str = "pcm") -> bytes:
        detected = AudioConverter.detect_format(data)
        fmt = src_format if src_format != "auto" else detected

        if fmt == "pcm":
            return data
        if fmt in ("wav", "mp3"):
            import wave
            try:
                buf = io.BytesIO(data) if fmt == "wav" else io.BytesIO(
                    AudioConverter._mp3_to_wav(data, src_sample_rate))
                with wave.open(buf, "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    ch = wf.getnchannels()
                    if ch > 1:
                        import audioop
                        frames = audioop.tomono(frames, wf.getsampwidth(), 0.5, 0.5)
                    return frames
            except Exception as e:
                log.warning(f"PCM conversion error: {e}")
                return data
        return data

    @staticmethod
    def to_mp3(data: bytes, src_sample_rate: int = 24000, src_format: str = "pcm",
               bitrate: str = "192k") -> bytes:
        try:
            import subprocess
            wav_data = AudioConverter.to_wav(data, src_sample_rate, src_format)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fin:
                fin.write(wav_data)
                wav_path = fin.name
            mp3_path = wav_path + ".mp3"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, mp3_path],
                    capture_output=True, timeout=30,
                )
                with open(mp3_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.unlink(wav_path)
                except Exception:
                    pass
                try:
                    os.unlink(mp3_path)
                except Exception:
                    pass
        except ImportError:
            log.warning("subprocess not available for MP3 encoding")
            return data
        except Exception as e:
            log.warning(f"MP3 encoding error: {e}")
            return data

    @staticmethod
    def _raw_to_wav(raw: bytes, sample_rate: int, channels: int = 1, bits: int = 16) -> bytes:
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(bits // 8)
            wf.setframerate(sample_rate)
            wf.writeframes(raw)
        return buf.getvalue()

    @staticmethod
    def _mp3_to_wav(data: bytes, target_sample_rate: int = 24000) -> bytes:
        try:
            import subprocess
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fin:
                fin.write(data)
                mp3_path = fin.name
            wav_path = mp3_path + ".wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", mp3_path,
                     "-acodec", "pcm_s16le", "-ar", str(target_sample_rate),
                     "-ac", "1", wav_path],
                    capture_output=True, timeout=30,
                )
                with open(wav_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.unlink(mp3_path)
                except Exception:
                    pass
                try:
                    os.unlink(wav_path)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"MP3->WAV conversion error: {e}")
            return data


def convert_sample_rate(data: bytes, src_rate: int, dst_rate: int,
                        channels: int = 1, bits: int = 16) -> bytes:
    if src_rate == dst_rate:
        return data

    import audioop
    try:
        converted, _ = audioop.ratecv(data, bits // 8, channels, src_rate, dst_rate, None)
        return converted
    except Exception as e:
        log.warning(f"sample rate conversion error ({src_rate}->{dst_rate}): {e}")
        return data


def normalize_audio(data: bytes, target_dbfs: float = -3.0,
                    sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    import audioop
    import struct
    import math

    sample_width = bits // 8

    rms = audioop.rms(data, sample_width)
    if rms == 0:
        return data

    current_dbfs = 20 * math.log10(rms / (2 ** (bits - 1)))
    gain_db = target_dbfs - current_dbfs
    gain_linear = 10 ** (gain_db / 20)

    return audioop.mul(data, sample_width, gain_linear)


def get_audio_meta(data: bytes, fmt: str = "auto") -> AudioMeta:
    detected = AudioConverter.detect_format(data)
    fmt = fmt if fmt != "auto" else detected

    if fmt == "wav":
        import wave
        try:
            with wave.open(io.BytesIO(data), "rb") as wf:
                nframes = wf.getnframes()
                rate = wf.getframerate()
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                duration = nframes / rate if rate > 0 else 0.0
                return AudioMeta(
                    format="wav", sample_rate=rate, channels=channels,
                    bits_per_sample=sampwidth * 8, duration=duration,
                )
        except Exception as e:
            log.warning(f"failed to read WAV header: {e}")

    if fmt == "mp3":
        try:
            import subprocess
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fin:
                fin.write(data)
                mp3_path = fin.name
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", "-show_streams", mp3_path],
                    capture_output=True, timeout=15, text=True,
                )
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    streams = info.get("streams", [{}])
                    fmt_info = info.get("format", {})
                    if streams:
                        s = streams[0]
                        rate = int(s.get("sample_rate", 24000))
                        channels = int(s.get("channels", 1))
                        duration = float(fmt_info.get("duration", 0.0))
                        return AudioMeta(
                            format="mp3", sample_rate=rate, channels=channels,
                            bits_per_sample=16, duration=duration,
                        )
            finally:
                try:
                    os.unlink(mp3_path)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"MP3 metadata error: {e}")

    duration = len(data) / (24000 * 2) if len(data) > 1 else 0.0
    return AudioMeta(
        format=fmt, sample_rate=24000, channels=1,
        bits_per_sample=16, duration=duration,
    )


def mix_audio(main_audio: bytes, overlay_audio: bytes, overlay_volume: float = 0.3,
              sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    import audioop

    sample_width = bits // 8

    if len(overlay_audio) > len(main_audio):
        overlay_audio = overlay_audio[:len(main_audio)]
    elif len(overlay_audio) < len(main_audio):
        silence = b"\x00" * (len(main_audio) - len(overlay_audio))
        overlay_audio = overlay_audio + silence

    overlay_audio = audioop.mul(overlay_audio, sample_width, overlay_volume)
    return audioop.add(main_audio, overlay_audio, sample_width)


def mix_with_background(main_audio: bytes, bgm_audio: bytes, bgm_volume: float = 0.2,
                        loop_bgm: bool = True, sample_rate: int = 24000) -> bytes:
    if not bgm_audio:
        return main_audio

    if loop_bgm and len(bgm_audio) > 0:
        repeats = (len(main_audio) // len(bgm_audio)) + 1
        bgm_audio = bgm_audio * repeats

    return mix_audio(main_audio, bgm_audio, overlay_volume=bgm_volume, sample_rate=sample_rate)


def generate_silence(duration: float, sample_rate: int = 24000,
                     channels: int = 1, bits: int = 16) -> bytes:
    num_samples = int(sample_rate * duration)
    return b"\x00" * (num_samples * channels * (bits // 8))


def generate_tone(frequency: float, duration: float, sample_rate: int = 24000,
                  volume: float = 0.5, bits: int = 16) -> bytes:
    import struct
    import math

    num_samples = int(sample_rate * duration)
    max_amp = (2 ** (bits - 1)) - 1
    samples: List[int] = []

    for i in range(num_samples):
        t = i / sample_rate
        value = int(math.sin(2 * math.pi * frequency * t) * max_amp * volume)
        samples.append(value)

    fmt = "<" + "h" * num_samples
    return struct.pack(fmt, *samples)


class AudioCache:
    def __init__(self, cache_dir: str = "cache/audio", ttl: int = 3600):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self._memory_cache: Dict[str, CacheEntry] = {}
        os.makedirs(cache_dir, exist_ok=True)
        self._load_index()

    def _key(self, data: bytes, suffix: str = "") -> str:
        return hashlib.sha256(data + suffix.encode()).hexdigest()

    def _load_index(self):
        idx_path = os.path.join(self.cache_dir, "index.json")
        if not os.path.exists(idx_path):
            return
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                index = json.load(f)
            now = time.time()
            for key, meta in list(index.items()):
                if now - meta.get("created_at", 0) > self.ttl:
                    continue
                data_path = os.path.join(self.cache_dir, f"{key}.bin")
                if os.path.exists(data_path):
                    with open(data_path, "rb") as bf:
                        data = bf.read()
                    self._memory_cache[key] = CacheEntry(
                        data=data,
                        meta=AudioMeta(**meta.get("meta", {})),
                        created_at=meta.get("created_at", now),
                    )
        except Exception as e:
            log.warning(f"failed to load audio cache index: {e}")

    def _save_index(self):
        idx_path = os.path.join(self.cache_dir, "index.json")
        index: Dict = {}
        for key, entry in self._memory_cache.items():
            index[key] = {
                "meta": {
                    "format": entry.meta.format,
                    "sample_rate": entry.meta.sample_rate,
                    "channels": entry.meta.channels,
                    "bits_per_sample": entry.meta.bits_per_sample,
                    "duration": entry.meta.duration,
                },
                "created_at": entry.created_at,
            }
        try:
            with open(idx_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except Exception as e:
            log.warning(f"failed to save audio cache index: {e}")

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._memory_cache.get(key)
        if entry and (time.time() - entry.created_at) < self.ttl:
            return entry
        if entry:
            del self._memory_cache[key]
        return None

    def put(self, data: bytes, meta: AudioMeta) -> str:
        key = self._key(data)
        self._memory_cache[key] = CacheEntry(data=data, meta=meta)
        try:
            data_path = os.path.join(self.cache_dir, f"{key}.bin")
            with open(data_path, "wb") as f:
                f.write(data)
            self._save_index()
        except Exception as e:
            log.warning(f"failed to write audio cache: {e}")
        return key

    def remove(self, key: str):
        self._memory_cache.pop(key, None)
        try:
            data_path = os.path.join(self.cache_dir, f"{key}.bin")
            if os.path.exists(data_path):
                os.remove(data_path)
            self._save_index()
        except Exception as e:
            log.warning(f"failed to remove audio cache entry: {e}")

    def clear(self):
        self._memory_cache.clear()
        try:
            for f in os.listdir(self.cache_dir):
                fpath = os.path.join(self.cache_dir, f)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"failed to clear audio cache: {e}")

    def cleanup_expired(self):
        now = time.time()
        expired = [k for k, v in self._memory_cache.items()
                   if now - v.created_at > self.ttl]
        for k in expired:
            self.remove(k)
        if expired:
            log.info(f"cleaned {len(expired)} expired audio cache entries")
