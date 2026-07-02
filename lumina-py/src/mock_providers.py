import asyncio
import logging
import random
from dataclasses import dataclass
from typing import AsyncGenerator, AsyncIterator, List, Optional, Tuple

log = logging.getLogger("lumina.mock")

MOCK_RESPONSES = [
    "你好呀！今天天气真不错，你出去走了走吗？",
    "我最近在学习一首新歌，等会儿唱给你听好不好？",
    "今天直播间来了好多新朋友，欢迎欢迎！",
    "你吃了吗？我最近发现一家超好吃的外卖。",
    "刚刚有个观众送了一个火箭，谢谢老板！",
    "大家想听什么歌？可以点歌哦！",
    "最近在看一部很有趣的动漫，推荐给你。",
    "你那边现在几点了？要注意休息哦。",
    "每天都要保持好心情，像我一样笑一个吧！",
    "这个故事有点长，让我慢慢讲给你听……",
    "哇，这个问题真有意思，让我想想怎么回答。",
    "谢谢大家的关注和支持，我会继续努力的！",
    "你平时有什么爱好吗？我平时就喜欢唱歌和聊天。",
    "今天试了一套新衣服，你觉得好看吗？",
    "互动时间到！我们来玩个游戏吧。",
]

MOCK_PHONEMES = ["a", "o", "e", "i", "u", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s"]

KEYWORD_RESPONSES = {
    "你好": "你好呀！欢迎来到 Lumina 虚拟人直播间！",
    "hello": "你好呀！欢迎来到 Lumina 虚拟人直播间！",
    "天气": "今天天气真不错，适合出去走走呢！不过在家陪我聊天也很好~",
    "名字": "我是 Lumina，你的 AI 虚拟人主播！很高兴认识你！",
    "你是谁": "我是 Lumina，你的 AI 虚拟人主播！很高兴认识你！",
}

MOCK_STT_TEXTS = ["你好", "今天天气不错", "唱首歌吧", "讲个故事", "哈哈哈", "加油"]


@dataclass
class MockSTTResult:
    text: str
    confidence: float = 0.8
    is_final: bool = True
    language: str = "zh"
    segments: Optional[List[dict]] = None


class MockLLM:
    def __init__(self, config: dict):
        self.cfg = config
        self.latency = config.get("latency", 0.3)

    async def chat(self, prompt: str, system: Optional[str] = None) -> str:
        await asyncio.sleep(self.latency)
        lower = prompt.lower()
        for kw, reply in KEYWORD_RESPONSES.items():
            if kw in prompt or kw in lower:
                return reply
        return random.choice(MOCK_RESPONSES)

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]:
        reply = await self.chat(prompt)
        delay = self.latency / max(len(reply), 1)
        for char in reply:
            await asyncio.sleep(delay)
            yield char


class MockTTS:
    def __init__(self, config: dict):
        self.cfg = config
        self.sample_rate = 24000
        self.latency = config.get("latency", 0.3)
        self._silence_frame = b"\x00" * (self.sample_rate * 2)

    def _estimate_duration(self, text: str) -> float:
        return max(0.5, len(text) * 0.08)

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        duration = self._estimate_duration(text)
        chunk_count = max(1, int(duration))
        chunk_delay = duration / chunk_count
        for _ in range(chunk_count):
            await asyncio.sleep(chunk_delay)
            yield self._silence_frame

    async def synthesize_full(self, text: str) -> Tuple[bytes, int, List]:
        await asyncio.sleep(self.latency)
        duration = self._estimate_duration(text)
        total_samples = int(duration * self.sample_rate)
        audio = b"\x00" * (total_samples * 2)
        phonemes = self._estimate_phonemes(text, len(audio))
        return audio, self.sample_rate, phonemes

    def _estimate_phonemes(self, text: str, audio_len: int) -> List[dict]:
        duration = audio_len / (self.sample_rate * 2)
        chars = list(text)
        if not chars:
            return []
        time_per_char = duration / len(chars)
        return [
            {
                "phoneme": random.choice(MOCK_PHONEMES),
                "start_time": i * time_per_char,
                "end_time": (i + 1) * time_per_char,
            }
            for i in range(len(chars))
        ]

    async def get_phoneme_timestamps(self, text: str) -> List[dict]:
        _, _, phonemes = await self.synthesize_full(text)
        return phonemes

    def subscribe(self, cb):
        pass

    async def cleanup(self):
        pass


class MockSTT:
    def __init__(self, config: dict):
        self.cfg = config
        self.latency = config.get("latency", 0.3)
        self._sample_rate = config.get("sample_rate", 16000)

    async def transcribe(self, audio_data: bytes, src_rate: int = None, src_format: str = "pcm") -> Optional[str]:
        await asyncio.sleep(self.latency)
        intensity = len(audio_data) / (self._sample_rate * 4)
        if intensity < 0.1:
            return None
        return random.choice(MOCK_STT_TEXTS)

    async def transcribe_with_details(self, audio_data: bytes, src_rate: int = None, src_format: str = "pcm") -> MockSTTResult:
        text = await self.transcribe(audio_data, src_rate, src_format)
        return MockSTTResult(text=text or "")

    async def stream_transcribe(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[MockSTTResult]:
        async for chunk in audio_stream:
            text = await self.transcribe(chunk)
            if text:
                yield MockSTTResult(text=text, is_final=False, confidence=0.7)
                return
        yield MockSTTResult(text=random.choice(MOCK_STT_TEXTS), is_final=True)

    async def cleanup(self):
        pass


class MockLipSync:
    def generate(self, text: str, duration: float) -> List[float]:
        total_frames = max(1, int(duration * 30))
        half = 0.5
        return [abs(half * (1 - 2 * abs(i / total_frames - 0.5))) for i in range(total_frames)]


def is_mock_enabled(config: dict) -> bool:
    mock_cfg = config.get("mock", {})
    if mock_cfg.get("enabled", False):
        return True
    if not mock_cfg.get("auto_fallback", True):
        return False
    try:
        import openai
        return False
    except ImportError:
        log.info("openai not installed, auto-enabling mock mode")
        return True
