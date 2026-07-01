import uuid
import time
import logging
from typing import Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

from .emotion_system import EmotionSystem
from .llm_service import LLMService

log = logging.getLogger("lumina.chat")


@dataclass
class Session:
    session_id: str
    history: List[Dict] = field(default_factory=list)
    emotion: EmotionSystem = field(default_factory=EmotionSystem)
    context: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    max_history: int = 50


class ChatHandler:
    def __init__(self, llm_service: LLMService, config: Optional[Dict] = None):
        self.llm = llm_service
        self.cfg = config or {}
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = self.cfg.get("session_timeout", 300)
        self.max_sessions = self.cfg.get("max_sessions", 1000)

    async def create_session(self, context: Optional[Dict] = None) -> str:
        if len(self.sessions) >= self.max_sessions:
            oldest = min(self.sessions.keys(), key=lambda k: self.sessions[k].last_active)
            await self.delete_session(oldest)
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = Session(
            session_id=session_id,
            context=context or {},
        )
        log.info(f"Created session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session:
            session.last_active = time.time()
        return session

    async def delete_session(self, session_id: str):
        self.sessions.pop(session_id, None)
        log.info(f"Deleted session: {session_id}")

    async def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        session = await self.get_session(session_id)
        if not session:
            return
        msg = {"role": role, "content": content, "timestamp": time.time()}
        if metadata:
            msg["metadata"] = metadata
        session.history.append(msg)
        if len(session.history) > session.max_history:
            session.history = session.history[-session.max_history:]

    async def build_context(self, session_id: str, user_input: str) -> str:
        session = await self.get_session(session_id)
        if not session:
            return user_input

        parts = []

        emotion = session.emotion.get_emotion_vector()
        dominant, intensity = session.emotion.get_dominant_emotion()
        parts.append(f"[System] Current emotional state: dominant={dominant}({intensity:.2f})")
        parts.append(f"[System] Emotion vector: {emotion}")

        live_ctx = session.context.get("live_stream", {})
        if live_ctx:
            parts.append(f"[Live Context] Audience count: {live_ctx.get('viewers', 0)}")
            parts.append(f"[Live Context] Stream status: {live_ctx.get('status', 'offline')}")

        user_ctx = session.context.get("user", {})
        if user_ctx:
            parts.append(f"[User Context] Name: {user_ctx.get('name', 'User')}")

        if session.history:
            recent = session.history[-5:]
            history_lines = [f"[{m['role']}]: {m['content'][:100]}" for m in recent]
            parts.append("[History]\n" + "\n".join(history_lines))

        parts.append(f"[User]: {user_input}")
        return "\n".join(parts)

    async def chat(self, session_id: str, user_input: str, system_prompt: Optional[str] = None) -> str:
        session = await self.get_session(session_id)
        if not session:
            session_id = await self.create_session()
            session = await self.get_session(session_id)

        await self.add_message(session_id, "user", user_input)
        context = await self.build_context(session_id, user_input)

        response = await self.llm.chat(context, system=system_prompt)

        emotion_tag = EmotionSystem.parse_emotion_tag(response)
        if emotion_tag:
            session.emotion.blend_emotion(emotion_tag)
            response = EmotionSystem.strip_emotion_tag(response)

        await self.add_message(session_id, "assistant", response)
        return response

    async def stream_chat(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        session = await self.get_session(session_id)
        if not session:
            session_id = await self.create_session()
            session = await self.get_session(session_id)

        await self.add_message(session_id, "user", user_input)
        context = await self.build_context(session_id, user_input)

        full_response = ""
        async for chunk in self.llm.stream_chat(context):
            full_response += chunk
            yield chunk

        emotion_tag = EmotionSystem.parse_emotion_tag(full_response)
        if emotion_tag:
            session.emotion.blend_emotion(emotion_tag)

        await self.add_message(session_id, "assistant", EmotionSystem.strip_emotion_tag(full_response))

    async def cleanup_expired_sessions(self):
        now = time.time()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session.last_active > self.session_timeout
        ]
        for sid in expired:
            await self.delete_session(sid)
        if expired:
            log.info(f"Cleaned up {len(expired)} expired sessions")
