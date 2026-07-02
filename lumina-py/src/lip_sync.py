import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("lumina.lipsync")


@dataclass
class LipFrame:
    time: float
    mouth_open: float = 0.0
    jaw_y: float = 0.0
    tongue_x: float = 0.0
    tongue_y: float = 0.0
    lip_width: float = 0.5


@dataclass
class LipSyncData:
    frames: List[LipFrame] = field(default_factory=list)
    total_duration: float = 0.0


EMOTION_LIP_OFFSETS: Dict[str, Dict[str, float]] = {
    "happy": {"mouth_open": 0.1, "lip_width": 0.15, "jaw_y": 0.05},
    "sad": {"mouth_open": -0.05, "lip_width": -0.1, "jaw_y": 0.02},
    "angry": {"mouth_open": 0.05, "lip_width": -0.08, "jaw_y": 0.1},
    "surprised": {"mouth_open": 0.3, "lip_width": 0.05, "jaw_y": 0.2},
    "loving": {"mouth_open": 0.08, "lip_width": 0.1, "jaw_y": 0.03},
    "anxious": {"mouth_open": -0.02, "lip_width": -0.05, "jaw_y": 0.05},
    "excited": {"mouth_open": 0.15, "lip_width": 0.12, "jaw_y": 0.08},
    "calm": {"mouth_open": 0.0, "lip_width": 0.0, "jaw_y": 0.0},
    "neutral": {"mouth_open": 0.0, "lip_width": 0.0, "jaw_y": 0.0},
    "confused": {"mouth_open": 0.03, "lip_width": -0.03, "jaw_y": 0.04},
}


PHONEME_VISEMES: Dict[str, Dict[str, float]] = {
    "a": {"mouth_open": 0.8, "jaw_y": 0.7, "lip_width": 0.5},
    "e": {"mouth_open": 0.5, "jaw_y": 0.5, "lip_width": 0.6},
    "i": {"mouth_open": 0.3, "jaw_y": 0.3, "lip_width": 0.7},
    "o": {"mouth_open": 0.6, "jaw_y": 0.5, "lip_width": 0.3},
    "u": {"mouth_open": 0.4, "jaw_y": 0.2, "lip_width": 0.2},
    "b": {"mouth_open": 0.1, "jaw_y": 0.1, "lip_width": 0.4},
    "p": {"mouth_open": 0.15, "jaw_y": 0.1, "lip_width": 0.4},
    "m": {"mouth_open": 0.05, "jaw_y": 0.05, "lip_width": 0.35},
    "f": {"mouth_open": 0.1, "jaw_y": 0.1, "lip_width": 0.5},
    "v": {"mouth_open": 0.15, "jaw_y": 0.1, "lip_width": 0.5},
    "d": {"mouth_open": 0.3, "jaw_y": 0.3, "lip_width": 0.5},
    "t": {"mouth_open": 0.35, "jaw_y": 0.3, "lip_width": 0.5},
    "n": {"mouth_open": 0.2, "jaw_y": 0.2, "lip_width": 0.5},
    "k": {"mouth_open": 0.4, "jaw_y": 0.4, "lip_width": 0.5},
    "g": {"mouth_open": 0.4, "jaw_y": 0.4, "lip_width": 0.5},
    "h": {"mouth_open": 0.3, "jaw_y": 0.3, "lip_width": 0.5},
    "l": {"mouth_open": 0.2, "jaw_y": 0.2, "lip_width": 0.5},
    "r": {"mouth_open": 0.25, "jaw_y": 0.2, "lip_width": 0.4},
    "s": {"mouth_open": 0.1, "jaw_y": 0.1, "lip_width": 0.6},
    "z": {"mouth_open": 0.15, "jaw_y": 0.1, "lip_width": 0.55},
    "sh": {"mouth_open": 0.15, "jaw_y": 0.15, "lip_width": 0.3},
    "ch": {"mouth_open": 0.3, "jaw_y": 0.25, "lip_width": 0.4},
    "zh": {"mouth_open": 0.25, "jaw_y": 0.2, "lip_width": 0.35},
    "w": {"mouth_open": 0.3, "jaw_y": 0.2, "lip_width": 0.3},
    "j": {"mouth_open": 0.2, "jaw_y": 0.2, "lip_width": 0.5},
    "q": {"mouth_open": 0.3, "jaw_y": 0.3, "lip_width": 0.4},
    "x": {"mouth_open": 0.15, "jaw_y": 0.15, "lip_width": 0.3},
    "sil": {"mouth_open": 0.0, "jaw_y": 0.0, "lip_width": 0.5},
    "silence": {"mouth_open": 0.0, "jaw_y": 0.0, "lip_width": 0.5},
}

PHONEME_CHAR_MAP: Dict[str, str] = {
    "a": "a", "ā": "a", "á": "a", "ǎ": "a", "à": "a",
    "o": "o", "ō": "o", "ó": "o", "ǒ": "o", "ò": "o",
    "e": "e", "ē": "e", "é": "e", "ě": "e", "è": "e",
    "i": "i", "ī": "i", "í": "i", "ǐ": "i", "ì": "i",
    "u": "u", "ū": "u", "ú": "u", "ǔ": "u", "ù": "u",
    "ü": "u", "ǖ": "u", "ǘ": "u", "ǚ": "u", "ǜ": "u",
    "b": "b", "p": "p", "m": "m", "f": "f",
    "d": "d", "t": "t", "n": "n", "l": "l",
    "g": "g", "k": "k", "h": "h",
    "j": "j", "q": "q", "x": "x",
    "zh": "zh", "ch": "ch", "sh": "sh", "r": "r",
    "z": "z", "c": "c", "s": "s",
    "y": "w",
}


class LipSyncGenerator:
    def __init__(self, config: dict = None):
        self.cfg = config or {}
        self.fps = self.cfg.get("fps", 30)
        self.frame_duration = 1.0 / self.fps
        self.emotion = self.cfg.get("emotion", "neutral")
        self.emotion_intensity = self.cfg.get("emotion_intensity", 0.5)
        self.smoothing = self.cfg.get("smoothing", 0.3)
        self._subscribers: List[Callable[[LipFrame], None]] = []

    def subscribe(self, cb: Callable[[LipFrame], None]):
        self._subscribers.append(cb)

    def _notify(self, frame: LipFrame):
        for cb in self._subscribers:
            try:
                cb(frame)
            except Exception as e:
                log.warning(f"subscriber error: {e}")

    def _apply_emotion(self, frame: LipFrame) -> LipFrame:
        offsets = EMOTION_LIP_OFFSETS.get(self.emotion, EMOTION_LIP_OFFSETS["neutral"])
        intensity = self.emotion_intensity
        frame.mouth_open += offsets.get("mouth_open", 0.0) * intensity
        frame.jaw_y += offsets.get("jaw_y", 0.0) * intensity
        frame.lip_width += offsets.get("lip_width", 0.0) * intensity
        frame.mouth_open = max(0.0, min(1.0, frame.mouth_open))
        frame.jaw_y = max(0.0, min(1.0, frame.jaw_y))
        frame.lip_width = max(0.0, min(1.0, frame.lip_width))
        return frame

    def _smooth_frames(self, frames: List[LipFrame]) -> List[LipFrame]:
        if len(frames) < 3:
            return frames
        smoothed: List[LipFrame] = [frames[0]]
        alpha = self.smoothing
        for i in range(1, len(frames) - 1):
            f = frames[i]
            f_prev = frames[i - 1]
            f_next = frames[i + 1]
            smoothed.append(LipFrame(
                time=f.time,
                mouth_open=f_prev.mouth_open * alpha + f.mouth_open * (1 - 2 * alpha) + f_next.mouth_open * alpha,
                jaw_y=f_prev.jaw_y * alpha + f.jaw_y * (1 - 2 * alpha) + f_next.jaw_y * alpha,
                tongue_x=f_prev.tongue_x * alpha + f.tongue_x * (1 - 2 * alpha) + f_next.tongue_x * alpha,
                tongue_y=f_prev.tongue_y * alpha + f.tongue_y * (1 - 2 * alpha) + f_next.tongue_y * alpha,
                lip_width=f_prev.lip_width * alpha + f.lip_width * (1 - 2 * alpha) + f_next.lip_width * alpha,
            ))
        smoothed.append(frames[-1])
        return smoothed

    def _char_to_phoneme(self, char: str) -> Optional[str]:
        if char in PHONEME_CHAR_MAP:
            return PHONEME_CHAR_MAP[char]
        import unicodedata
        if "CJK" in unicodedata.name(char, ""):
            return "a"
        return None

    def _text_to_viseme_sequence(self, text: str) -> List[Tuple[str, float]]:
        text = text.lower()
        import re
        tokens = re.findall(r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùüǖǘǚǜ]+|[^a-zāáǎàēéěèīíǐìōóǒòūúǔùüǖǘǚǜ]+", text)
        sequence: List[Tuple[str, float]] = []
        for token in tokens:
            if re.match(r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùüǖǘǚǜ]+", token):
                for char in token:
                    phoneme = self._char_to_phoneme(char)
                    if phoneme:
                        sequence.append((phoneme, 0.08))
                    else:
                        sequence.append(("a", 0.08))
                sequence.append(("sil", 0.02))
            else:
                duration = len(token) * 0.05
                sequence.append(("sil", duration))
        return sequence

    def from_text(self, text: str, duration: float = None) -> LipSyncData:
        if not text or not text.strip():
            num_frames = max(1, int(1.0 * self.fps))
            frames = [LipFrame(time=i * self.frame_duration) for i in range(num_frames)]
            for f in frames:
                self._apply_emotion(f)
            return LipSyncData(frames=frames, total_duration=1.0)

        visemes = self._text_to_viseme_sequence(text)
        total_viseme_duration = sum(d for _, d in visemes)

        if duration is not None and duration > 0:
            scale = duration / total_viseme_duration
        else:
            scale = 1.0

        frames: List[LipFrame] = []
        current_time = 0.0

        for phoneme, dur in visemes:
            scaled_dur = dur * scale
            viseme = PHONEME_VISEMES.get(phoneme, PHONEME_VISEMES["sil"])
            num_subframes = max(1, int(scaled_dur / self.frame_duration))

            for i in range(num_subframes):
                t = current_time + (i / num_subframes) * scaled_dur
                frame_time = min(t, current_time + scaled_dur)
                frame = LipFrame(
                    time=frame_time,
                    mouth_open=viseme.get("mouth_open", 0.0),
                    jaw_y=viseme.get("jaw_y", 0.0),
                    tongue_x=viseme.get("tongue_x", 0.0),
                    tongue_y=viseme.get("tongue_y", 0.0),
                    lip_width=viseme.get("lip_width", 0.5),
                )
                self._apply_emotion(frame)
                frames.append(frame)

            current_time += scaled_dur

        frames = self._smooth_frames(frames)

        if duration is not None and frames:
            final_time = frames[-1].time
            if final_time < duration:
                remaining = duration - final_time
                extra_frames = max(1, int(remaining * self.fps))
                last = frames[-1]
                for i in range(1, extra_frames + 1):
                    t = final_time + i * self.frame_duration
                    frame = LipFrame(
                        time=t,
                        mouth_open=max(0.0, last.mouth_open * (1 - i / extra_frames)),
                        jaw_y=max(0.0, last.jaw_y * (1 - i / extra_frames)),
                    )
                    self._apply_emotion(frame)
                    frames.append(frame)

        return LipSyncData(frames=frames, total_duration=current_time)

    def from_audio_amplitude(self, audio_data: bytes, sample_rate: int = 24000) -> LipSyncData:
        import struct

        if not audio_data:
            return LipSyncData()

        samples_per_frame = int(sample_rate / self.fps)
        frames: List[LipFrame] = []
        num_samples = len(audio_data) // 2
        duration = num_samples / sample_rate

        for i in range(0, num_samples, samples_per_frame):
            chunk = audio_data[i * 2: (i + samples_per_frame) * 2]
            if len(chunk) < 2:
                continue

            amplitudes: List[int] = []
            for j in range(0, len(chunk), 2):
                if j + 1 < len(chunk):
                    sample = struct.unpack("<h", chunk[j:j + 2])[0]
                    amplitudes.append(abs(sample))

            if amplitudes:
                rms = math.sqrt(sum(a * a for a in amplitudes) / len(amplitudes))
            else:
                rms = 0

            max_amp = 32768.0
            normalized = min(1.0, rms / (max_amp * 0.3))
            mouth_open = max(0.0, normalized)
            jaw_y = mouth_open * 0.8
            t = i / sample_rate

            frame = LipFrame(
                time=t,
                mouth_open=mouth_open,
                jaw_y=jaw_y,
                lip_width=0.3 + mouth_open * 0.4,
            )
            self._apply_emotion(frame)
            frames.append(frame)

        frames = self._smooth_frames(frames)
        return LipSyncData(frames=frames, total_duration=duration)

    def from_phoneme_timings(self, phoneme_timings: List) -> LipSyncData:
        if not phoneme_timings:
            return LipSyncData()

        frames: List[LipFrame] = []
        all_phonemes = phoneme_timings
        total_duration = max(p.end_time for p in all_phonemes) if all_phonemes else 0.0

        t = 0.0
        while t < total_duration:
            matching = [p for p in all_phonemes if p.start_time <= t < p.end_time]
            if matching:
                phoneme = matching[0].phoneme.lower()
            else:
                phoneme = "sil"

            viseme = PHONEME_VISEMES.get(phoneme, PHONEME_VISEMES["sil"])
            frame = LipFrame(
                time=t,
                mouth_open=viseme.get("mouth_open", 0.0),
                jaw_y=viseme.get("jaw_y", 0.0),
                tongue_x=viseme.get("tongue_x", 0.0),
                tongue_y=viseme.get("tongue_y", 0.0),
                lip_width=viseme.get("lip_width", 0.5),
            )
            self._apply_emotion(frame)
            frames.append(frame)
            t += self.frame_duration

        frames = self._smooth_frames(frames)
        return LipSyncData(frames=frames, total_duration=total_duration)

    def set_emotion(self, emotion: str, intensity: float = 0.5):
        if emotion in EMOTION_LIP_OFFSETS:
            self.emotion = emotion
            self.emotion_intensity = max(0.0, min(1.0, intensity))
        else:
            log.warning(f"unknown emotion: {emotion}")

    def set_fps(self, fps: int):
        if fps > 0:
            self.fps = fps
            self.frame_duration = 1.0 / fps

    def interpolate_frames(self, data: LipSyncData, playback_time: float) -> Optional[LipFrame]:
        if not data.frames:
            return None
        if playback_time <= data.frames[0].time:
            return data.frames[0]
        if playback_time >= data.frames[-1].time:
            return data.frames[-1]

        for i in range(len(data.frames) - 1):
            cur = data.frames[i]
            nxt = data.frames[i + 1]
            if cur.time <= playback_time <= nxt.time:
                if nxt.time - cur.time < 0.0001:
                    return cur
                ratio = (playback_time - cur.time) / (nxt.time - cur.time)
                return LipFrame(
                    time=playback_time,
                    mouth_open=cur.mouth_open + (nxt.mouth_open - cur.mouth_open) * ratio,
                    jaw_y=cur.jaw_y + (nxt.jaw_y - cur.jaw_y) * ratio,
                    tongue_x=cur.tongue_x + (nxt.tongue_x - cur.tongue_x) * ratio,
                    tongue_y=cur.tongue_y + (nxt.tongue_y - cur.tongue_y) * ratio,
                    lip_width=cur.lip_width + (nxt.lip_width - cur.lip_width) * ratio,
                )
        return data.frames[-1]

    async def stream_from_text(self, text: str, duration: float = None) -> LipSyncData:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self.from_text, text, duration)
        for frame in data.frames:
            self._notify(frame)
            await asyncio.sleep(self.frame_duration)
        return data

    async def stream_from_phonemes(self, phoneme_timings: List) -> LipSyncData:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self.from_phoneme_timings, phoneme_timings)
        for frame in data.frames:
            self._notify(frame)
        return data
