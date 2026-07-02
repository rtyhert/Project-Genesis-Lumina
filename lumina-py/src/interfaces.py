"""Abstract interfaces for key dependencies — enables loose coupling and testability."""
from typing import Protocol, AsyncGenerator, List, Dict, Optional, runtime_checkable


@runtime_checkable
class LLMInterface(Protocol):
    async def chat(self, prompt: str, system: Optional[str] = None) -> str: ...

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]: ...


@runtime_checkable
class TTSInterface(Protocol):
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]: ...

    async def synthesize_full(self, text: str) -> tuple[bytes, int, list]: ...


@runtime_checkable
class STTInterface(Protocol):
    async def transcribe(self, audio_data: bytes, src_rate: int = None, src_format: str = "pcm") -> Optional[str]: ...


@runtime_checkable
class AgentInterface(Protocol):
    """Abstract interface for agent systems (CrewManager, etc.)."""
    async def run_task_async(self, task_description: str, agent_name: str = "chat") -> str: ...

    async def generate_stream_script(self, context: Dict) -> object: ...

    async def chat_with_emotion(self, user_input: str, history: Optional[List[Dict]] = None) -> object: ...


@runtime_checkable
class NeuroEngineInterface(Protocol):
    async def start(self): ...

    async def stop(self): ...

    async def get_status(self) -> Dict: ...

    async def generate_live_script(self) -> str: ...
