import re
import time
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("upage.emotion")

class EmotionSystem:
    EMOTIONS = ["happy", "sad", "angry", "surprised", "fearful", "disgusted", "neutral"]

    EMOTION_ACTIONS = {
        "happy": ["smile", "laugh", "cheer", "wave"],
        "sad": ["sigh", "lower_head", "pause"],
        "angry": ["frown", "raise_voice", "gesture"],
        "surprised": ["eyes_wide", "gasp", "lean_back"],
        "fearful": ["shiver", "look_away", "hesitate"],
        "disgusted": ["wrinkle_nose", "turn_away", "shake_head"],
        "neutral": ["nod", "blink", "tilt_head"],
    }

    def __init__(self, config: Optional[Dict] = None):
        self.cfg = config or {}
        self.decay_rate = self.cfg.get("decay_rate", 0.1)
        self.blend_threshold = self.cfg.get("blend_threshold", 0.3)
        self._emotions: Dict[str, float] = {e: 0.0 for e in self.EMOTIONS}
        self._emotions["neutral"] = 1.0
        self._last_update = time.time()

    def set_emotion(self, name: str, intensity: float = 1.0):
        if name not in self.EMOTIONS:
            log.warning(f"Unknown emotion: {name}")
            return
        self._apply_decay()
        self._emotions[name] = max(0.0, min(1.0, intensity))
        self._last_update = time.time()

    def get_dominant_emotion(self) -> Tuple[str, float]:
        self._apply_decay()
        return max(self._emotions.items(), key=lambda x: x[1])

    def get_emotion_vector(self) -> Dict[str, float]:
        self._apply_decay()
        return dict(self._emotions)

    def blend_emotion(self, name: str, intensity: float = 0.5):
        if name not in self.EMOTIONS:
            return
        self._apply_decay()
        current = self._emotions[name]
        self._emotions[name] = max(0.0, min(1.0, current + intensity * (1.0 - current)))
        for emo in self.EMOTIONS:
            if emo != name:
                self._emotions[emo] *= (1.0 - intensity * self.blend_threshold)
        self._last_update = time.time()

    def _apply_decay(self):
        elapsed = time.time() - self._last_update
        if elapsed <= 0:
            return
        factor = max(0.0, 1.0 - self.decay_rate * elapsed)
        for emo in self.EMOTIONS:
            if emo != "neutral":
                self._emotions[emo] *= factor
        self._emotions["neutral"] = max(0.0, 1.0 - sum(v for k, v in self._emotions.items() if k != "neutral"))

    @classmethod
    def parse_emotion_tag(cls, text: str) -> Optional[str]:
        match = re.search(r'\[emotion:(\w+)\]', text)
        if match and match.group(1) in cls.EMOTIONS:
            return match.group(1)
        return None

    @classmethod
    def strip_emotion_tag(cls, text: str) -> str:
        return re.sub(r'\[emotion:\w+\]\s*', '', text).strip()

    def get_suggested_actions(self) -> List[str]:
        dominant, intensity = self.get_dominant_emotion()
        actions = self.EMOTION_ACTIONS.get(dominant, self.EMOTION_ACTIONS["neutral"])
        count = max(1, min(3, int(intensity * 3)))
        return actions[:count]

    def reset(self):
        self._emotions = {e: 0.0 for e in self.EMOTIONS}
        self._emotions["neutral"] = 1.0
        self._last_update = time.time()
