import asyncio
import time
import grpc
import yaml
import logging
from concurrent import futures
from pathlib import Path

from .crew_manager import CrewManager
from .neuro_engine import NeuroEngine
from .tts_engine import TTSEngine
from .stt_engine import STTEngine
from .llm_service import LLMService
from .chat_handler import ChatHandler

import sys
sys.path.append(str(Path(__file__).parent.parent / "upage-proto" / "src"))
sys.path.append(str(Path(__file__).parent.parent / "upage-proto" / "build"))

log = logging.getLogger("upage")

class UpageServer:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            self.cfg = yaml.safe_load(f)
        self._setup_logging()
        self.start_time = time.time()
        self.llm = LLMService(self.cfg["llm"])
        self.crew = CrewManager(self.cfg["crew"], self.llm)
        self.neuro = NeuroEngine(self.cfg.get("neuro", {}), self.crew)
        self.tts = TTSEngine(self.cfg.get("tts", {}))
        self.stt = STTEngine(self.cfg.get("stt", {}))
        self.chat_handler = ChatHandler(self.llm, self.cfg.get("chat", {}))

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def _setup_logging(self):
        cfg = self.cfg.get("logging", {})
        logging.basicConfig(
            level=getattr(logging, cfg.get("level", "INFO").upper()),
            filename=cfg.get("file", "logs/upage.log"),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self.log = logging.getLogger("upage")

    async def start_grpc(self):
        server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[("grpc.max_send_message_length", 50 * 1024 * 1024)]
        )
        port = self.cfg["server"]["port"]
        server.add_insecure_port(f"[::]:{port}")
        await server.start()
        self.log.info(f"gRPC server started on port {port}")
        await server.wait_for_termination()
