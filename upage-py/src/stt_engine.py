import logging
from typing import Optional

log = logging.getLogger("upage.stt")

class STTEngine:
    def __init__(self, config):
        self.cfg = config
        self.engine = config.get("engine", "whisper")
        self.model = config.get("model", "base")

    async def transcribe(self, audio_data: bytes) -> Optional[str]:
        log.info(f"STT: transcribing {len(audio_data)} bytes")
        try:
            import whisper
            model = whisper.load_model(self.model)
            result = model.transcribe(audio_data, language="zh")
            return result["text"].strip()
        except ImportError:
            log.warning("whisper not installed, returning placeholder")
            return "[语音识别未安装]"
