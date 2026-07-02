import logging
import re
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lumina.sentiment")

EMOTION_KEYWORD_SETS: Dict[str, frozenset] = {
    "happy": frozenset({"开心", "高兴", "哈哈", "好棒", "太棒了", "喜欢", "爱了", "快乐", "幸福", "微笑", "嘻嘻", "笑死", "hhh", "lol", "nice", "great", "wonderful", "amazing", "love", "cute", "beautiful"}),
    "sad": frozenset({"难过", "伤心", "哭了", "不开心", "悲伤", "痛苦", "失落", "孤独", "寂寞", "泪", "呜", "t_t", ":(", "sad", "cry", "depressed", "lonely", "heartbroken", "miss"}),
    "angry": frozenset({"生气", "愤怒", "烦", "讨厌", "可恶", "气死", "受不了", "暴躁", "火大", "滚", ":((", "angry", "mad", "furious", "annoyed", "hate", "damn"}),
    "surprised": frozenset({"哇", "天哪", "真的吗", "不会吧", "震惊", "惊讶", "居然", "竟然", "卧槽", "omg", "wow", "really", "unbelievable", "shocked", "amazing", "what"}),
    "fearful": frozenset({"害怕", "恐怖", "吓人", "紧张", "担心", "焦虑", "不安", "慌", "怕", "scared", "afraid", "terrified", "nervous", "worried", "anxious", "panic"}),
    "disgusted": frozenset({"恶心", "讨厌", "反胃", "呕吐", "yuck", "eww", "disgusting", "gross", "awful", "terrible"}),
    "neutral": frozenset(),
}

INTENSIFIERS = frozenset({"非常", "很", "太", "超级", "极度", "特别", "十分", "相当", "有点", "有些", "so", "very", "really", "extremely", "super", "too"})

NEGATION_WORDS = frozenset({"不", "没", "别", "不要", "不是", "不会", "没有", "not", "no", "never", "don't", "doesn't", "didn't", "won't"})

EMOJI_MAP: Dict[str, str] = {
    "😊": "happy", "😄": "happy", "😂": "happy", "🤣": "happy",
    "🥰": "happy", "😍": "happy", "😘": "happy", "😁": "happy",
    "😢": "sad", "😭": "sad", "🥺": "sad", "😞": "sad",
    "😡": "angry", "🤬": "angry", "😤": "angry", "😠": "angry",
    "😱": "surprised", "😲": "surprised", "🤯": "surprised",
    "😨": "fearful", "😰": "fearful", "😖": "fearful",
    "🤢": "disgusted", "🤮": "disgusted",
}

WORD_PATTERN = re.compile(r"\S+")
EMOTION_TAG = re.compile(r"\[emotion:(\w+)\]")
EMOTION_NAMES = list(EMOTION_KEYWORD_SETS.keys())

_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")


def _build_emotion_patterns() -> Dict[str, List[re.Pattern]]:
    patterns = {}
    for emotion, keywords in EMOTION_KEYWORD_SETS.items():
        if not keywords:
            continue
        expr_list = []
        for kw in keywords:
            if _HAS_CJK.search(kw):
                expr_list.append(re.compile(re.escape(kw)))
            else:
                expr_list.append(re.compile(r"\b" + re.escape(kw) + r"\b"))
        patterns[emotion] = expr_list
    return patterns


_EMOTION_PATTERNS = _build_emotion_patterns()


class SentimentAnalyzer:
    def analyze(self, text: str) -> Dict[str, float]:
        scores = {emotion: 0.0 for emotion in EMOTION_NAMES}

        if not text or not text.strip():
            scores["neutral"] = 1.0
            return scores

        text_lower = text.lower()

        for emotion, patterns in _EMOTION_PATTERNS.items():
            for pat in patterns:
                match = pat.search(text_lower)
                if match:
                    score = 1.0
                    idx = match.start()
                    prefix = text_lower[:idx].rstrip()
                    if prefix:
                        prev_word = prefix.split()[-1]
                        if prev_word in INTENSIFIERS:
                            score = 1.5
                        elif prev_word in NEGATION_WORDS:
                            score = -0.5
                    scores[emotion] += score

        for char in text:
            emotion = EMOJI_MAP.get(char)
            if emotion:
                scores[emotion] = scores.get(emotion, 0) + 0.3

        if all(v == 0 for v in scores.values()):
            scores["neutral"] = 1.0
            return scores

        min_val = min(scores.values())
        if min_val < 0:
            scores = {k: v - min_val for k, v in scores.items()}

        total = sum(scores.values()) or 1.0
        if total != 1.0:
            inv_total = 1.0 / total
            scores = {k: v * inv_total for k, v in scores.items()}

        return scores

    def dominant_emotion(self, text: str) -> Tuple[str, float]:
        scores = self.analyze(text)
        dominant = max(scores.items(), key=lambda x: x[1])
        return dominant

    def extract_emotion_tag(self, text: str) -> Optional[str]:
        match = EMOTION_TAG.search(text)
        return match.group(1) if match else None
