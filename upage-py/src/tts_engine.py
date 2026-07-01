import asyncio
import logging
from typing import AsyncIterator

log = logging.getLogger("upage.tts")

class TTSEngine:
    def __init__(self, config):
        self.cfg = config
        self.engine = config.get("engine", "edge-tts")
        self.voice = config.get("voice", "zh-CN-XiaoxiaoNeural")
        self.speed = config.get("speed", 1.0)

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        log.info(f"TTS: synthesizing {len(text)} chars")
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except ImportError:
            log.warning("edge-tts not installed, using silent audio")
            yield b""
