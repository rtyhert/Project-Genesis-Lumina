import time
import grpc
import yaml
import logging
import os
import sys
from pathlib import Path

from crew_manager import CrewManager
from neuro_engine import NeuroEngine
from tts_engine import TTSEngine
from stt_engine import STTEngine
from llm_service import LLMService
from chat_handler import ChatHandler
from grpc_retry import create_default_wrapper
from config_schema import validate_config

PROTO_DIR = Path(__file__).resolve().parent.parent
sys.path.extend(str(p) for p in [
    str(PROTO_DIR / "lumina-proto" / "src"),
    str(PROTO_DIR / "lumina-proto" / "build"),
    str(PROTO_DIR / "lumina-bridge"),
] if p not in sys.path)

log = logging.getLogger("lumina")

try:
    from lumina_bridge.grpc import LuminaVirtualHumanServicer
    import lumina_pb2_grpc as pb2_grpc
    _HAS_GRPC = True
except ImportError:
    LuminaVirtualHumanServicer = None
    pb2_grpc = None
    _HAS_GRPC = False
    log.warning("gRPC stubs not compiled; run lumina-proto/build_proto.bat")


class LuminaServer:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            raw_cfg = yaml.safe_load(f)
        self.cfg = validate_config(raw_cfg)
        self._setup_logging()
        self.start_time = time.time()
        self.mock_mode = self._detect_mock_mode()
        self.persona = self.cfg.persona

        if self.mock_mode:
            from mock_providers import MockLLM, MockTTS, MockSTT, MockLipSync
            self.log.info("Running in MOCK mode — no real AI services required")
            self.llm = MockLLM(self.cfg.mock.model_dump())
            self.tts = MockTTS(self.cfg.mock.model_dump())
            self.stt = MockSTT(self.cfg.mock.model_dump())
            self.lip_sync = MockLipSync()
        else:
            self.llm = LLMService(self.cfg.llm.model_dump())
            self.tts = TTSEngine(self.cfg.tts.model_dump())
            self.stt = STTEngine(self.cfg.stt.model_dump())
            self.lip_sync = None

        self.crew = CrewManager(self.cfg.crew.model_dump(), self.llm)
        self.neuro = NeuroEngine(self.cfg.neuro.model_dump(), self.crew)
        self.chat_handler = ChatHandler(self.llm, self.cfg.chat.model_dump())
        self.grpc_retry = create_default_wrapper()
        self._grpc_server = None
        self._nekoclaw = None
        self._apply_persona()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def _detect_mock_mode(self) -> bool:
        env_mock = os.environ.get("LUMINA_MOCK", "")
        if env_mock == "1":
            return True
        if env_mock == "0":
            return False
        if self.cfg.mock.enabled:
            return True
        if self.cfg.mock.auto_fallback:
            try:
                import openai
                return False
            except ImportError:
                self.log.info("openai not installed, auto-enabling mock mode")
                return True
        return False

    def _apply_persona(self):
        if self.persona == "nekoclaw":
            try:
                from neko_persona import (
                    PERSONA_SYSTEM_PROMPT,
                    NEKO_PROACTIVE_TEMPLATES,
                    NEKO_GIFT_TABLE,
                    NEKO_GIFT_REACTIONS,
                    NEKO_EMOTION_ACTIONS,
                    NEKO_STATE_DURATIONS,
                    get_neko_action_for_emotion,
                    build_neko_persona_prompt,
                    translate_to_neko_speech,
                )
                self.log.info("Loading nekoclaw cat-girl persona...")
                self.chat_handler.persona_prompt = PERSONA_SYSTEM_PROMPT
                self.chat_handler.persona_builder = build_neko_persona_prompt
                self.chat_handler.persona_translate = translate_to_neko_speech

                if hasattr(self.neuro, "proactive_templates"):
                    self.neuro.proactive_templates = NEKO_PROACTIVE_TEMPLATES
                if hasattr(self.neuro, "gift_table"):
                    self.neuro.gift_table = NEKO_GIFT_TABLE
                if hasattr(self.neuro, "state_durations"):
                    self.neuro.state_durations = NEKO_STATE_DURATIONS

                self._nekoclaw = {
                    "emotion_actions": NEKO_EMOTION_ACTIONS,
                    "gift_reactions": NEKO_GIFT_REACTIONS,
                    "action_for_emotion": get_neko_action_for_emotion,
                }
                self.log.info("nekoclaw persona activated — nyaa~!")
            except ImportError as e:
                self.log.warning("nekoclaw persona module not available: %s", e)
        else:
            self.log.info("Using default persona: %s", self.persona)

    def get_persona_action(self, emotion: str) -> list:
        if self._nekoclaw:
            return self._nekoclaw["action_for_emotion"](emotion)
        from emotion_system import EmotionSystem
        return EmotionSystem.EMOTION_ACTIONS.get(emotion, ["blink"])

    def _setup_logging(self):
        cfg = self.cfg.logging
        logging.basicConfig(
            level=getattr(logging, cfg.level),
            filename=cfg.file,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self.log = logging.getLogger("lumina")

    async def start_grpc(self):
        if not _HAS_GRPC:
            self.log.warning("gRPC disabled: compile proto first (run lumina-proto/build_proto.bat)")
            return

        self._grpc_server = grpc.aio.server(
            options=[("grpc.max_send_message_length", 50 * 1024 * 1024)]
        )
        servicer = LuminaVirtualHumanServicer(
            tts=self.tts, stt=self.stt,
            neuro=self.neuro, bridge=None
        )
        pb2_grpc.add_VirtualHumanServicer_to_server(servicer, self._grpc_server)
        port = self.cfg.server.port
        self._grpc_server.add_insecure_port(f"[::]:{port}")
        await self._grpc_server.start()
        self.log.info(f"gRPC server started on port {port}")
        await self._grpc_server.wait_for_termination()

    async def get_full_status(self) -> dict:
        neuro_status = await self.neuro.get_status()
        return {
            "uptime": self.uptime_seconds,
            "mock_mode": self.mock_mode,
            "grpc_enabled": _HAS_GRPC,
            **neuro_status,
        }
