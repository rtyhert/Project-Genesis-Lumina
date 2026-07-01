import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional, Tuple, Callable, Awaitable

log = logging.getLogger("lumina.tts")


@dataclass
class PhonemeTiming:
    phoneme: str
    start_time: float
    end_time: float


@dataclass
class TTSCacheEntry:
    audio: bytes
    sample_rate: int
    phonemes: List[PhonemeTiming]
    created_at: float = field(default_factory=time.time)


class TTSEngine:
    def __init__(self, config: dict):
        self.cfg = config
        self.engine = config.get("engine", "edge-tts")
        self.voice = config.get("voice", "zh-CN-XiaoxiaoNeural")
        self.speed = config.get("speed", 1.0)
        self.pitch = config.get("pitch", 0.0)
        self.volume = config.get("volume", 1.0)
        self.lang = config.get("language", "zh-CN")
        self.cache_dir = config.get("cache_dir", "cache/tts")
        self.cache_enabled = config.get("cache_enabled", True)
        self.cache_ttl = config.get("cache_ttl", 3600)
        self._cache: Dict[str, TTSCacheEntry] = {}
        self._subscribers: List[Callable[[str, bytes], Awaitable[None]]] = []

        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
            self._load_disk_cache()

    def subscribe(self, cb: Callable[[str, bytes], Awaitable[None]]):
        self._subscribers.append(cb)

    async def _notify(self, text: str, audio: bytes):
        for cb in self._subscribers:
            try:
                await cb(text, audio)
            except Exception as e:
                log.warning(f"Subscriber error: {e}")

    def _cache_key(self, text: str, voice: str, speed: float, pitch: float, volume: float) -> str:
        raw = f"{text}|{voice}|{speed}|{pitch}|{volume}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_disk_cache(self):
        index_path = os.path.join(self.cache_dir, "index.json")
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index: Dict[str, dict] = json.load(f)
            now = time.time()
            for key, meta in list(index.items()):
                if now - meta.get("created_at", 0) > self.cache_ttl:
                    continue
                audio_path = os.path.join(self.cache_dir, f"{key}.mp3")
                phoneme_path = os.path.join(self.cache_dir, f"{key}.phonemes.json")
                if os.path.exists(audio_path) and os.path.exists(phoneme_path):
                    with open(audio_path, "rb") as af:
                        audio = af.read()
                    with open(phoneme_path, "r", encoding="utf-8") as pf:
                        phonemes = [PhonemeTiming(**p) for p in json.load(pf)]
                    self._cache[key] = TTSCacheEntry(
                        audio=audio,
                        sample_rate=meta.get("sample_rate", 24000),
                        phonemes=phonemes,
                        created_at=meta.get("created_at", now),
                    )
            log.info(f"Loaded {len(self._cache)} entries from TTS disk cache")
        except Exception as e:
            log.warning(f"Failed to load TTS disk cache: {e}")

    def _save_disk_cache(self, key: str, entry: TTSCacheEntry):
        if not self.cache_enabled:
            return
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            audio_path = os.path.join(self.cache_dir, f"{key}.mp3")
            phoneme_path = os.path.join(self.cache_dir, f"{key}.phonemes.json")
            with open(audio_path, "wb") as f:
                f.write(entry.audio)
            with open(phoneme_path, "w", encoding="utf-8") as f:
                json.dump(
                    [{"phoneme": p.phoneme, "start_time": p.start_time, "end_time": p.end_time}
                     for p in entry.phonemes],
                    f,
                    ensure_ascii=False,
                )
            index_path = os.path.join(self.cache_dir, "index.json")
            index: Dict = {}
            if os.path.exists(index_path):
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
            index[key] = {"sample_rate": entry.sample_rate, "created_at": entry.created_at}
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
        except Exception as e:
            log.warning(f"Failed to save TTS disk cache: {e}")

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        log.info(f"synthesizing {len(text)} chars, engine={self.engine}")

        result = await self._synthesize_full(text)
        if result is None:
            log.warning("all backends failed, yielding empty audio")
            yield b""
            return

        audio, sample_rate, phonemes = result
        if self.cache_enabled:
            key = self._cache_key(text, self.voice, self.speed, self.pitch, self.volume)
            self._cache[key] = TTSCacheEntry(
                audio=audio, sample_rate=sample_rate, phonemes=phonemes
            )
            self._save_disk_cache(key, self._cache[key])

        chunk_size = sample_rate * 2
        for i in range(0, len(audio), chunk_size):
            yield audio[i:i + chunk_size]

    async def synthesize_full(self, text: str) -> Tuple[bytes, int, List[PhonemeTiming]]:
        log.info(f"synthesizing full audio: {len(text)} chars")
        result = await self._synthesize_full(text)
        if result is None:
            return b"", 24000, []
        audio, sample_rate, phonemes = result
        if self.cache_enabled:
            key = self._cache_key(text, self.voice, self.speed, self.pitch, self.volume)
            self._cache[key] = TTSCacheEntry(
                audio=audio, sample_rate=sample_rate, phonemes=phonemes
            )
            self._save_disk_cache(key, self._cache[key])
        await self._notify(text, audio)
        return audio, sample_rate, phonemes

    async def _synthesize_full(self, text: str) -> Optional[Tuple[bytes, int, List[PhonemeTiming]]]:
        if not text or not text.strip():
            return b"", 24000, []

        if self.cache_enabled:
            key = self._cache_key(text, self.voice, self.speed, self.pitch, self.volume)
            cached = self._cache.get(key)
            if cached and (time.time() - cached.created_at) < self.cache_ttl:
                log.info(f"cache hit for text: {text[:40]}")
                return cached.audio, cached.sample_rate, cached.phonemes

        engine = self.engine
        backends = [engine, "edge-tts", "openai", "pyttsx3"]

        visited = set()
        for be in backends:
            if be in visited:
                continue
            visited.add(be)
            try:
                if be == "edge-tts":
                    return await self._synthesize_edge_tts(text)
                elif be == "openai":
                    return await self._synthesize_openai(text)
                elif be == "pyttsx3":
                    return await self._synthesize_pyttsx3(text)
            except ImportError as e:
                log.debug(f"backend {be} not available: {e}")
                continue
            except Exception as e:
                log.warning(f"backend {be} failed: {e}")
                continue
        return None

    async def _synthesize_edge_tts(self, text: str) -> Tuple[bytes, int, List[PhonemeTiming]]:
        import edge_tts

        voice = self.voice
        rate_str = f"{int((self.speed - 1.0) * 100):+d}%"
        pitch_str = f"{int(self.pitch * 100):+d}Hz"
        volume_str = f"{int((self.volume - 1.0) * 100):+d}%"

        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str, volume=volume_str)
        audio_chunks: List[bytes] = []
        phonemes: List[PhonemeTiming] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                phonemes.append(PhonemeTiming(
                    phoneme=chunk.get("text", ""),
                    start_time=chunk.get("offset", 0) / 1e7,
                    end_time=(chunk.get("offset", 0) + chunk.get("duration", 0)) / 1e7,
                ))

        audio = b"".join(audio_chunks)
        return audio, 24000, phonemes

    async def _synthesize_openai(self, text: str) -> Tuple[bytes, int, List[PhonemeTiming]]:
        import openai
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.cfg.get("openai_api_key"))
        voice = self.voice if "alloy" in self.voice or "echo" in self.voice or "fable" in self.voice or "onyx" in self.voice or "nova" in self.voice or "shimmer" in self.voice else "nova"

        resp = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            speed=self.speed,
            response_format="wav",
        )
        audio = resp.content

        phonemes = self._estimate_phonemes(text, len(audio), 24000)
        return audio, 24000, phonemes

    async def _synthesize_pyttsx3(self, text: str) -> Tuple[bytes, int, List[PhonemeTiming]]:
        import tempfile
        import pyttsx3
        import soundfile as sf

        engine = pyttsx3.init()
        rate = int(engine.getProperty("rate") * self.speed)
        engine.setProperty("rate", rate)
        vol = min(1.0, max(0.0, self.volume))
        engine.setProperty("volume", vol)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            data, sr = sf.read(tmp_path)
            if data.dtype == "float64":
                data = data.astype("float32")
            audio = (data * 32767).astype("int16").tobytes()
            phonemes = self._estimate_phonemes(text, len(audio), sr)
            return audio, sr, phonemes
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _estimate_phonemes(self, text: str, audio_len: int, sample_rate: int) -> List[PhonemeTiming]:
        duration = audio_len / (sample_rate * 2)
        words = text.split()
        if not words:
            return []
        time_per_word = duration / len(words)
        phonemes: List[PhonemeTiming] = []
        t = 0.0
        for w in words:
            phonemes.append(PhonemeTiming(
                phoneme=w,
                start_time=t,
                end_time=t + time_per_word,
            ))
            t += time_per_word
        return phonemes

    async def batch_synthesize(self, texts: List[str]) -> List[Tuple[bytes, int, List[PhonemeTiming]]]:
        async def _single(t: str) -> Tuple[str, bytes, int, List[PhonemeTiming]]:
            audio, sr, phonemes = await self.synthesize_full(t)
            return t, audio, sr, phonemes

        tasks = [_single(t) for t in texts]
        results: List[Tuple[bytes, int, List[PhonemeTiming]]] = []
        for coro in asyncio.as_completed(tasks):
            text, audio, sr, phonemes = await coro
            results.append((audio, sr, phonemes))
        return results

    async def get_phoneme_timestamps(self, text: str) -> List[PhonemeTiming]:
        _, _, phonemes = await self.synthesize_full(text)
        return phonemes

    def clear_cache(self):
        self._cache.clear()
        index_path = os.path.join(self.cache_dir, "index.json")
        if os.path.exists(index_path):
            os.remove(index_path)
        log.info("TTS cache cleared")

    async def cleanup(self):
        self.clear_cache()
