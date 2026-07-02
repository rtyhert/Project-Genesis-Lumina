"""Config validation schema — validates config.yaml at startup using pydantic."""
import logging
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import os

log = logging.getLogger("lumina.config")


class MockConfig(BaseModel):
    """Mock mode — zero-dependency demo mode for development/CI."""
    enabled: bool = Field(default=False, description="Force mock mode (overrides auto_fallback)")
    latency: float = Field(default=0.3, description="Simulated response latency in seconds")
    auto_fallback: bool = Field(default=True, description="Auto-enable mock when real services unavailable")


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    provider: str = Field(default="openai", description="Provider name (only openai supported)")
    model: str = Field(default="gpt-4", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Response creativity")
    max_tokens: int = Field(default=1024, ge=1, le=32768, description="Max response tokens")


class TTSConfig(BaseModel):
    """Text-to-Speech configuration."""
    engine: Literal["edge-tts", "openai", "pyttsx3"] = Field(default="edge-tts", description="TTS backend")
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="Voice name")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    pitch: float = Field(default=0.0, description="Pitch offset (Hz)")
    volume: float = Field(default=1.0, ge=0.0, le=2.0, description="Volume multiplier")
    language: str = Field(default="zh-CN", description="Language code")
    cache_enabled: bool = Field(default=True, description="Enable disk+memory cache")
    cache_dir: str = Field(default="cache/tts", description="Cache directory path")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    max_cache_entries: int = Field(default=200, ge=10, description="Max in-memory cache entries")


class STTConfig(BaseModel):
    """Speech-to-Text configuration."""
    engine: Literal["whisper", "faster-whisper", "vosk"] = Field(default="whisper", description="STT backend")
    model: str = Field(default="base", description="Model size (tiny/base/small/medium/large)")
    language: str = Field(default="zh", description="Target language code")
    sample_rate: int = Field(default=16000, description="Audio sample rate")
    vad_enabled: bool = Field(default=True, description="Enable voice activity detection")
    device: str = Field(default="auto", description="Compute device (auto/cpu/cuda)")
    compute_type: str = Field(default="float16", description="Precision (float16/int8)")
    vosk_model_path: str = Field(default="models/vosk", description="Path to Vosk model directory")


class LipSyncConfig(BaseModel):
    """Lip-sync generation configuration."""
    fps: int = Field(default=30, description="Target frames per second")
    emotion: str = Field(default="neutral", description="Default emotion offset")
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="Emotion effect strength")
    smoothing: float = Field(default=0.3, ge=0.0, le=1.0, description="Temporal smoothing factor")


class CrewConfig(BaseModel):
    """CrewAI agent configuration."""
    max_iterations: int = Field(default=5, ge=1, le=100, description="Max iterations per agent")
    verbose: bool = Field(default=True, description="Enable agent logging")


class ServerConfig(BaseModel):
    """Server network configuration."""
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=50051, ge=1024, le=65535, description="gRPC server port")
    rest_port: int = Field(default=8000, ge=1024, le=65535, description="REST API port")


class NeuroConfig(BaseModel):
    """Neuro engine — live stream simulation configuration."""
    stream_mode: str = Field(default="simulate", description="Stream mode (simulate)")
    audience_size: int = Field(default=10, ge=1, le=1000, description="Simulated viewer count")
    auto_reply: bool = Field(default=True, description="Auto-reply to danmaku events")
    proactive_interval: int = Field(default=30, ge=5, le=600, description="Proactive utterance interval (s)")


class ChatConfig(BaseModel):
    """Chat handler configuration."""
    session_timeout: int = Field(default=300, ge=10, description="Session idle timeout (seconds)")
    max_sessions: int = Field(default=1000, ge=1, description="Max concurrent sessions")
    decay_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Emotion decay rate")
    blend_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Emotion blend factor")


class MonitoringConfig(BaseModel):
    """Prometheus monitoring configuration."""
    enabled: bool = Field(default=False, description="Enable Prometheus endpoint")
    port: int = Field(default=9090, ge=1024, le=65535, description="Prometheus server port")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", description="Log level")
    file: str = Field(default="logs/lumina.log", description="Log file path")


class AuthConfig(BaseModel):
    """API Key authentication.
    
    When enabled, all requests (except exclude_paths) must include
    'Authorization: Bearer <api_key>' header.
    """
    enabled: bool = Field(default=False, description="Enable API key authentication")
    api_key: str = Field(default="", description="API key for Bearer token validation")
    exclude_paths: list = Field(default=["/health", "/metrics", "/docs", "/openapi.json"],
                                description="Paths excluded from authentication")


class RateLimitConfig(BaseModel):
    """Rate limiting configuration (requires slowapi package).
    
    Limits requests per IP address to prevent abuse.
    """
    enabled: bool = Field(default=False, description="Enable rate limiting")
    requests_per_minute: int = Field(default=60, ge=1, le=10000, description="Max requests per minute per IP")


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    hot_reload: bool = Field(default=False, description="Enable uvicorn hot-reload (dev only)")
    persona: str = Field(default="default", description="Persona name (default/nekoclaw)")

    @field_validator("persona", mode="before")
    @classmethod
    def coerce_persona(cls, v):
        if isinstance(v, dict):
            return v.get("name", "default")
        return v if isinstance(v, str) else "default"
    mock: MockConfig = MockConfig()
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    stt: STTConfig = STTConfig()
    lip_sync: LipSyncConfig = LipSyncConfig()
    crew: CrewConfig = CrewConfig()
    neuro: NeuroConfig = NeuroConfig()
    chat: ChatConfig = ChatConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    auth: AuthConfig = AuthConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    logging: LoggingConfig = LoggingConfig()

    @model_validator(mode="after")
    def check_mock_auto_fallback(self):
        if self.mock.auto_fallback and self.mock.enabled:
            log.info("Mock mode enabled; auto_fallback will be used if services unavailable")
        return self

    @model_validator(mode="after")
    def check_stt_engine_deps(self):
        if self.stt.engine == "vosk":
            if not os.path.exists(self.stt.vosk_model_path):
                log.warning("stt.engine=vosk but vosk_model_path '%s' not found", self.stt.vosk_model_path)
        if self.stt.engine == "whisper":
            valid = ("tiny", "base", "small", "medium", "large", "large-v2", "large-v3")
            if self.stt.model not in valid:
                log.warning("stt.model='%s' may not be a valid Whisper model name; expected one of %s",
                            self.stt.model, valid)
        return self

    @model_validator(mode="after")
    def check_tts_cache_dir(self):
        if self.tts.cache_enabled:
            p = Path(self.tts.cache_dir)
            p.mkdir(parents=True, exist_ok=True)
        return self

    @field_validator("logging")
    @classmethod
    def ensure_log_dir(cls, v: LoggingConfig):
        log_dir = Path(v.file).parent
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
        return v


def validate_config(raw: dict) -> AppConfig:
    """Validate raw dict from yaml.safe_load against AppConfig schema.

    Returns validated AppConfig on success.
    Raises pydantic.ValidationError on failure with detailed field errors.
    """
    return AppConfig.model_validate(raw)
