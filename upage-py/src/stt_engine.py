import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import AsyncIterator, Callable, List, Optional, Tuple

log = logging.getLogger("upage.stt")


@dataclass
class STTResult:
    text: str
    confidence: float
    is_final: bool
    language: str
    segments: List[dict] = None


@dataclass
class VADState:
    is_speaking: bool = False
    silence_duration: float = 0.0
    speech_duration: float = 0.0
    energy_threshold: float = 500.0
    min_speech_duration: float = 0.3
    min_silence_duration: float = 0.8


class STTEngine:
    def __init__(self, config: dict):
        self.cfg = config
        self.engine = config.get("engine", "whisper")
        self.model_name = config.get("model", "base")
        self.lang = config.get("language", "zh")
        self.sample_rate = config.get("sample_rate", 16000)
        self.vad_enabled = config.get("vad_enabled", True)
        self.vad = VADState()
        self._model = None
        self._model_lock = asyncio.Lock()
        self._transcribe_subscribers: List[Callable[[STTResult], None]] = []
        self._interim_subscribers: List[Callable[[STTResult], None]] = []
        self._audio_buffer: List[bytes] = []

    def on_transcribe(self, cb: Callable[[STTResult], None]):
        self._transcribe_subscribers.append(cb)

    def on_interim(self, cb: Callable[[STTResult], None]):
        self._interim_subscribers.append(cb)

    async def _load_model(self):
        async with self._model_lock:
            if self._model is not None:
                return self._model

            if self.engine == "faster-whisper":
                try:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        self.model_name,
                        device=self.cfg.get("device", "auto"),
                        compute_type=self.cfg.get("compute_type", "float16"),
                    )
                    log.info(f"faster-whisper model loaded: {self.model_name}")
                except ImportError:
                    log.warning("faster-whisper not available, falling back to whisper")
                    self.engine = "whisper"

            if self.engine == "whisper" or self._model is None:
                try:
                    import whisper

                    self._model = whisper.load_model(self.model_name)
                    log.info(f"whisper model loaded: {self.model_name}")
                except ImportError:
                    log.warning("whisper not available, will use vosk fallback")
                    self.engine = "vosk"

            if self.engine == "vosk" or self._model is None:
                try:
                    from vosk import Model as VoskModel

                    model_path = self.cfg.get("vosk_model_path", "models/vosk")
                    if os.path.exists(model_path):
                        self._model = VoskModel(model_path)
                    else:
                        log.warning(f"Vosk model not found at {model_path}, downloading small model")
                        import urllib.request
                        import zipfile

                        os.makedirs(model_path, exist_ok=True)
                        url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
                        zip_path = os.path.join(model_path, "model.zip")
                        urllib.request.urlretrieve(url, zip_path)
                        with zipfile.ZipFile(zip_path, "r") as zf:
                            zf.extractall(model_path)
                        os.remove(zip_path)
                        extracted = [d for d in os.listdir(model_path)
                                     if os.path.isdir(os.path.join(model_path, d))]
                        if extracted:
                            self._model = VoskModel(os.path.join(model_path, extracted[0]))
                            log.info("Vosk model loaded")
                except ImportError:
                    log.warning("vosk not available either, STT disabled")

            return self._model

    def _convert_audio(self, audio_data: bytes, src_rate: int = None, src_format: str = "pcm") -> Tuple[bytes, int]:
        import io
        import wave

        src_rate = src_rate or self.sample_rate
        target_rate = self.sample_rate

        if src_format == "mp3":
            try:
                import pydub
                from pydub import AudioSegment

                seg = AudioSegment.from_mp3(io.BytesIO(audio_data))
                seg = seg.set_frame_rate(target_rate).set_channels(1).set_sample_width(2)
                raw = seg.raw_data
                return raw, seg.frame_rate
            except ImportError:
                import struct
                import audioop

                try:
                    raw, rate = self._decode_mp3_ffmpeg(audio_data)
                    if rate != target_rate:
                        raw, _ = audioop.ratecv(raw, 2, 1, rate, target_rate, None)
                    return raw, target_rate
                except Exception:
                    log.warning("MP3 conversion failed, using raw data")
                    return audio_data, src_rate

        elif src_format == "wav":
            try:
                with io.BytesIO(audio_data) as buf:
                    with wave.open(buf, "rb") as wf:
                        frames = wf.readframes(wf.getnframes())
                        rate = wf.getframerate()
                        channels = wf.getnchannels()
                        import audioop
                        if channels > 1:
                            frames = audioop.tomono(frames, 2, 0.5, 0.5)
                        if rate != target_rate:
                            frames, _ = audioop.ratecv(frames, 2, 1, rate, target_rate, None)
                        return frames, target_rate
            except Exception as e:
                log.warning(f"WAV conversion error: {e}")
                return audio_data, src_rate

        else:
            import audioop
            if src_rate != target_rate:
                try:
                    audio_data, _ = audioop.ratecv(audio_data, 2, 1, src_rate, target_rate, None)
                except Exception:
                    pass
            return audio_data, target_rate

    def _decode_mp3_ffmpeg(self, data: bytes) -> Tuple[bytes, int]:
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fin:
            fin.write(data)
            mp3_path = fin.name
        wav_path = mp3_path + ".wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, "-acodec", "pcm_s16le",
                 "-ar", str(self.sample_rate), "-ac", "1", wav_path],
                capture_output=True, timeout=30,
            )
            import wave
            with wave.open(wav_path, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
                return raw, wf.getframerate()
        finally:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass
            try:
                os.unlink(wav_path)
            except Exception:
                pass

    def _vad_process(self, chunk: bytes) -> bool:
        import struct
        import audioop

        if not self.vad_enabled:
            return True

        if len(chunk) < 2:
            return self.vad.is_speaking

        rms = audioop.rms(chunk, 2)
        frame_duration = len(chunk) / (self.sample_rate * 2)

        if rms > self.vad.energy_threshold:
            self.vad.speech_duration += frame_duration
            self.vad.silence_duration = 0.0
            if not self.vad.is_speaking and self.vad.speech_duration >= self.vad.min_speech_duration:
                self.vad.is_speaking = True
                self.vad.speech_duration = 0.0
        else:
            if self.vad.is_speaking:
                self.vad.silence_duration += frame_duration
                if self.vad.silence_duration >= self.vad.min_silence_duration:
                    self.vad.is_speaking = False
                    self.vad.speech_duration = 0.0
                    self.vad.silence_duration = 0.0
            else:
                self.vad.silence_duration = 0.0

        return self.vad.is_speaking

    async def transcribe(self, audio_data: bytes, src_rate: int = None, src_format: str = "pcm") -> Optional[str]:
        log.info(f"transcribing {len(audio_data)} bytes, format={src_format}")

        audio_data, rate = self._convert_audio(audio_data, src_rate, src_format)

        model = await self._load_model()
        if model is None:
            log.warning("no STT model available, returning placeholder")
            return "[语音识别未安装]"

        try:
            if self.engine == "faster-whisper" or (hasattr(model, "transcribe")):
                import numpy as np
                samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                if hasattr(model, "transcribe") and self.engine != "faster-whisper":
                    result = model.transcribe(samples, language=self.lang)
                    text = result.get("text", "").strip()
                    if not text:
                        return ""
                    return text
                else:
                    segments, info = model.transcribe(samples, language=self.lang)
                    text = "".join(seg.text for seg in segments).strip()
                    if not text:
                        return ""
                    return text
            elif self.engine == "vosk":
                import json
                if hasattr(model, "Recognize"):
                    rec = model.Recognize(audio_data)
                    if rec:
                        result = json.loads(rec)
                        return result.get("text", "").strip()
                return ""
            else:
                log.warning(f"unknown engine type: {self.engine}")
                return ""
        except Exception as e:
            log.error(f"transcription error: {e}")
            return ""

    async def transcribe_with_details(self, audio_data: bytes, src_rate: int = None,
                                       src_format: str = "pcm") -> STTResult:
        text = await self.transcribe(audio_data, src_rate, src_format)
        return STTResult(
            text=text or "",
            confidence=1.0 if text else 0.0,
            is_final=True,
            language=self.lang,
        )

    async def stream_transcribe(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[STTResult]:
        buffer = bytearray()
        chunk_duration = 0.03
        chunk_size = int(self.sample_rate * 2 * chunk_duration)

        async for chunk in audio_stream:
            buffer.extend(chunk)

            while len(buffer) >= chunk_size:
                frame = bytes(buffer[:chunk_size])
                buffer = buffer[chunk_size:]

                is_speech = self._vad_process(frame)
                if not is_speech:
                    continue

                self._audio_buffer.append(frame)
                if len(self._audio_buffer) * chunk_duration >= 1.0:
                    audio_data = b"".join(self._audio_buffer)
                    try:
                        text = await self.transcribe(audio_data)
                        if text:
                            result = STTResult(
                                text=text,
                                confidence=0.8,
                                is_final=False,
                                language=self.lang,
                            )
                            for cb in self._interim_subscribers:
                                try:
                                    cb(result)
                                except Exception:
                                    pass
                            yield result
                    except Exception as e:
                        log.debug(f"interim transcribe error: {e}")
                    self._audio_buffer = []

        if self._audio_buffer:
            audio_data = b"".join(self._audio_buffer)
            try:
                text = await self.transcribe(audio_data)
                if text:
                    result = STTResult(
                        text=text,
                        confidence=0.9,
                        is_final=True,
                        language=self.lang,
                    )
                    for cb in self._transcribe_subscribers:
                        try:
                            cb(result)
                        except Exception:
                            pass
                    yield result
            except Exception as e:
                log.error(f"final transcribe error: {e}")

    async def transcribe_file(self, file_path: str) -> Optional[str]:
        import soundfile as sf
        try:
            data, sr = sf.read(file_path)
            if data.dtype == "float64":
                data = data.astype("float32")
            audio_bytes = (data * 32767).astype("int16").tobytes()
            return await self.transcribe(audio_bytes, src_rate=sr)
        except Exception as e:
            log.error(f"file transcribe error: {e}")
            return None

    async def cleanup(self):
        self._audio_buffer.clear()
        self._model = None
        log.info("STT engine cleaned up")
