import math
import re
import time
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lumina.emotion")

EMOTION_TAG_REGEX = re.compile(r"\[emotion:(\w+)\]")
EMOTION_TAG_STRIP = re.compile(r"\[emotion:\w+\]\s*")


class EmotionSystem:
    EMOTIONS = ["happy", "sad", "angry", "surprised", "fearful", "disgusted", "neutral"]
    EMOTION_SET = frozenset(EMOTIONS)

    EMOTION_ACTIONS = {
        "happy": ["smile", "laugh", "cheer", "wave"],
        "sad": ["sigh", "lower_head", "pause"],
        "angry": ["frown", "raise_voice", "gesture"],
        "surprised": ["eyes_wide", "gasp", "lean_back"],
        "fearful": ["shiver", "look_away", "hesitate"],
        "disgusted": ["wrinkle_nose", "turn_away", "shake_head"],
        "neutral": ["nod", "blink", "tilt_head"],
    }

    def __init__(self, config: Optional[Dict] = None, action_map: Optional[Dict[str, List[str]]] = None):
        self.cfg = config or {}
        self.decay_rate = self.cfg.get("decay_rate", 0.1)
        self.blend_threshold = self.cfg.get("blend_threshold", 0.3)
        self._emotions: Dict[str, float] = {e: 0.0 for e in self.EMOTIONS}
        self._actions = action_map or self.EMOTION_ACTIONS
        self._emotions["neutral"] = 1.0
        self._last_update = time.time()

    def set_emotion(self, name: str, intensity: float = 1.0):
        if name not in self.EMOTION_SET:
            log.warning(f"Unknown emotion: {name}")
            return
        self._apply_decay()
        intensity = max(0.0, min(1.0, intensity))
        other_sum = sum(v for k, v in self._emotions.items() if k != name)
        if other_sum > 0:
            scale = (1.0 - intensity) / other_sum
            for emo in self.EMOTIONS:
                if emo != name:
                    self._emotions[emo] *= scale
        else:
            remaining = (1.0 - intensity) / (len(self.EMOTIONS) - 1)
            for emo in self.EMOTIONS:
                if emo != name:
                    self._emotions[emo] = remaining
        self._emotions[name] = intensity
        self._last_update = time.time()

    def get_dominant_emotion(self) -> Tuple[str, float]:
        self._apply_decay()
        best_emo = "neutral"
        best_val = 0.0
        for emo, val in self._emotions.items():
            if val > best_val:
                best_val = val
                best_emo = emo
        if best_val == 0.0:
            return ("neutral", 0.0)
        return best_emo, best_val

    def get_emotion_vector(self) -> Dict[str, float]:
        self._apply_decay()
        return dict(self._emotions)

    def blend_emotion(self, name: str, intensity: float = 0.5):
        if name not in self.EMOTION_SET:
            return
        self._apply_decay()
        current = self._emotions[name]
        self._emotions[name] = max(0.0, min(1.0, current + intensity * (1.0 - current)))
        factor = 1.0 - intensity * self.blend_threshold
        for emo in self.EMOTIONS:
            if emo != name:
                self._emotions[emo] *= factor
        self._normalize()
        self._last_update = time.time()

    def _normalize(self):
        total = sum(self._emotions.values())
        if total > 0:
            inv_total = 1.0 / total
            for emo in self.EMOTIONS:
                self._emotions[emo] *= inv_total

    def _apply_decay(self):
        elapsed = time.time() - self._last_update
        if elapsed <= 0:
            return
        factor = math.exp(-self.decay_rate * elapsed)
        for emo in self.EMOTIONS:
            self._emotions[emo] *= factor
        total = sum(self._emotions.values())
        if total > 1e-10:
            inv_total = 1.0 / total
            for emo in self.EMOTIONS:
                self._emotions[emo] *= inv_total

    @classmethod
    def parse_emotion_tag(cls, text: str) -> Optional[str]:
        match = EMOTION_TAG_REGEX.search(text)
        if match and match.group(1) in cls.EMOTION_SET:
            return match.group(1)
        return None

    @classmethod
    def strip_emotion_tag(cls, text: str) -> str:
        return EMOTION_TAG_STRIP.sub("", text).strip()

    def get_suggested_actions(self) -> List[str]:
        dominant, intensity = self.get_dominant_emotion()
        actions = self._actions.get(dominant, self._actions.get("neutral", ["blink"]))
        return actions[:max(1, min(3, int(intensity * 3)))]

    def reset(self):
        self._emotions = {e: 0.0 for e in self.EMOTIONS}
        self._emotions["neutral"] = 1.0
        self._last_update = time.time()
