import asyncio
import uuid
import time
import logging
from typing import Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from heapq import heappush, heappop

from emotion_system import EmotionSystem
from llm_service import LLMService
from sentiment import SentimentAnalyzer

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
    sentiment: Optional[Dict] = None


class ChatHandler:
    def __init__(self, llm_service: LLMService, config: Optional[Dict] = None):
        self.llm = llm_service
        self.cfg = config or {}
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = self.cfg.get("session_timeout", 300)
        self.max_sessions = self.cfg.get("max_sessions", 1000)
        self.sentiment = SentimentAnalyzer()
        self._expiry_heap: List[tuple] = []
        self._deleted_sessions: set = set()
        self._cleanup_task: Optional[asyncio.Task] = None
        self.persona_prompt: Optional[str] = None
        self.persona_builder = None
        self.persona_translate = None

    def start_cleanup_task(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup_task(self):
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, StopAsyncIteration):
                pass

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(60)
            try:
                await self.cleanup_expired_sessions()
            except Exception as e:
                log.error(f"Periodic cleanup error: {e}")

    async def create_session(self, context: Optional[Dict] = None) -> str:
        if len(self.sessions) >= self.max_sessions:
            oldest = min(self.sessions.keys(), key=lambda k: self.sessions[k].last_active)
            await self.delete_session(oldest)
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = Session(
            session_id=session_id,
            context=context or {},
        )
        heappush(self._expiry_heap, (time.time() + self.session_timeout, session_id))
        log.info(f"Created session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session:
            session.last_active = time.time()
        return session

    async def delete_session(self, session_id: str):
        self.sessions.pop(session_id, None)
        self._deleted_sessions.add(session_id)
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

        if self.persona_prompt:
            parts.append(f"[Persona]\n{self.persona_prompt}")

        dominant, intensity = session.emotion.get_dominant_emotion()
        parts.append(f"[System] Current emotional state: dominant={dominant}({intensity:.2f})")

        if session.sentiment:
            sent_dominant = max(session.sentiment, key=session.sentiment.get)
            parts.append(f"[System] User sentiment: dominant={sent_dominant}, scores={session.sentiment}")

        live_ctx = session.context.get("live_stream", {})
        if live_ctx:
            parts.append(f"[Live Context] Audience count: {live_ctx.get('viewers', 0)}")
            parts.append(f"[Live Context] Stream status: {live_ctx.get('status', 'offline')}")

        user_ctx = session.context.get("user", {})
        if user_ctx:
            parts.append(f"[User Context] Name: {user_ctx.get('name', 'User')}")

        if session.history:
            recent = session.history[-5:]
            parts.append("[History]\n" + "\n".join(f"[{m['role']}]: {m['content'][:100]}" for m in recent))

        parts.append(f"[User]: {user_input}")
        return "\n".join(parts)

    def _process_sentiment(self, session: Session, user_input: str):
        sentiment_scores = self.sentiment.analyze(user_input)
        session.sentiment = sentiment_scores
        dominant_sentiment, intensity = max(sentiment_scores.items(), key=lambda x: x[1])
        if dominant_sentiment != "neutral" and intensity > 0.3:
            session.emotion.blend_emotion(dominant_sentiment, intensity)
        return sentiment_scores

    def _parse_emotion_tag(self, session: Session, text: str) -> str:
        emotion_tag = EmotionSystem.parse_emotion_tag(text)
        if emotion_tag:
            session.emotion.blend_emotion(emotion_tag)
            text = EmotionSystem.strip_emotion_tag(text)
        return text

    async def _ensure_session(self, session_id: Optional[str] = None) -> str:
        if session_id and session_id in self.sessions:
            return session_id
        return await self.create_session()

    async def chat(self, session_id: str, user_input: str, system_prompt: Optional[str] = None) -> str:
        session_id = await self._ensure_session(session_id)
        session = self.sessions[session_id]

        self._process_sentiment(session, user_input)
        context = await self.build_context(session_id, user_input)
        await self.add_message(session_id, "user", user_input)

        sp = system_prompt or self.persona_prompt
        response = await self.llm.chat(context, system=sp)
        response = self._parse_emotion_tag(session, response)

        if self.persona_translate:
            response = self.persona_translate(response)

        await self.add_message(session_id, "assistant", response)
        return response

    async def stream_chat(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        session_id = await self._ensure_session(session_id)
        session = self.sessions[session_id]

        self._process_sentiment(session, user_input)
        context = await self.build_context(session_id, user_input)
        await self.add_message(session_id, "user", user_input)

        full_response = []
        async for chunk in self.llm.stream_chat(context):
            full_response.append(chunk)
            yield chunk

        text = "".join(full_response)
        text = self._parse_emotion_tag(session, text)
        if self.persona_translate:
            text = self.persona_translate(text)
        await self.add_message(session_id, "assistant", text)

    async def cleanup_expired_sessions(self):
        now = time.time()
        while self._expiry_heap and self._expiry_heap[0][0] <= now:
            _, sid = heappop(self._expiry_heap)
            self._deleted_sessions.discard(sid)
            if sid in self.sessions and now - self.sessions[sid].last_active > self.session_timeout:
                await self.delete_session(sid)
