import asyncio
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

import sys
sys.path.append(str(Path(__file__).parent.parent / "upage-proto" / "src"))
sys.path.append(str(Path(__file__).parent.parent / "upage-proto" / "build"))

class UpageServer:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            self.cfg = yaml.safe_load(f)
        self._setup_logging()
        self.llm = LLMService(self.cfg["llm"])
        self.crew = CrewManager(self.cfg["crew"], self.llm)
        self.neuro = NeuroEngine(self.cfg["neuro"], self.crew)
        self.tts = TTSEngine(self.cfg["tts"])
        self.stt = STTEngine(self.cfg["stt"])

    def _setup_logging(self):
        cfg = self.cfg["logging"]
        logging.basicConfig(
            level=getattr(logging, cfg["level"].upper()),
            filename=cfg["file"],
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

    async def start_rest(self):
        import uvicorn
        from fastapi import FastAPI
        app = FastAPI(title="upage-py", version="0.1.0")
        rest_port = self.cfg["server"]["rest_port"]
        config = uvicorn.Config(app, host="0.0.0.0", port=rest_port, log_level="info")
        server = uvicorn.Server(config)
        self.log.info(f"REST server starting on port {rest_port}")
        await server.serve()
