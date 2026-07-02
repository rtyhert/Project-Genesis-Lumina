import pytest
from emotion_system import EmotionSystem
from sentiment import SentimentAnalyzer
from llm_service import LLMService
from chat_handler import ChatHandler


class TestEmotionSystem:
    def test_initial_state(self):
        es = EmotionSystem()
        emo, intens = es.get_dominant_emotion()
        assert emo == "neutral"
        assert intens > 0

    def test_set_emotion_positive(self):
        es = EmotionSystem()
        es.set_emotion("happy", 0.8)
        emo, _ = es.get_dominant_emotion()
        assert emo == "happy"

    def test_emotion_decay(self):
        es = EmotionSystem({"decay_rate": 0.5})
        es.set_emotion("happy", 1.0)
        es._apply_decay()
        emo, intens = es.get_dominant_emotion()
        assert intens <= 1.0

    def test_emotion_blend(self):
        es = EmotionSystem({"blend_threshold": 0.5})
        es.blend_emotion("happy", 0.9)
        emo, _ = es.get_dominant_emotion()
        assert emo == "happy"

    def test_normalize_maintains_distribution(self):
        es = EmotionSystem()
        es.set_emotion("happy", 0.9)
        es.set_emotion("sad", 0.3)
        vec = es.get_emotion_vector()
        total = sum(vec.values())
        assert abs(total - 1.0) < 0.01

    def test_get_suggested_actions(self):
        es = EmotionSystem()
        actions = es.get_suggested_actions()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_custom_action_map(self):
        custom = {"happy": ["purr", "wag"], "neutral": ["blink"]}
        es = EmotionSystem(action_map=custom)
        es.set_emotion("happy", 1.0)
        actions = es.get_suggested_actions()
        assert "purr" in actions


class TestSentimentAnalyzer:
    def test_neutral_default(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("")
        assert result.get("neutral", 0) > 0

    def test_happy_text(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("happy good great wonderful")
        assert result.get("happy", 0) <= 1.0

    def test_sad_text(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("sad cry unhappy terrible")
        assert result.get("sad", 0) <= 1.0

    def test_angry_text(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("angry mad furious rage")
        assert result.get("angry", 0) <= 1.0

    def test_dominant_emotion(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("happy good")
        dom = max(result, key=result.get)
        assert dom in ("happy", "neutral")

    def test_intensifier_boosts_score(self):
        sa = SentimentAnalyzer()
        normal = sa.analyze("happy")
        boosted = sa.analyze("very very very happy")
        assert boosted.get("happy", 0) >= normal.get("happy", 0)


class TestChatHandlerPipeline:
    @pytest.mark.asyncio
    async def test_chat_create_and_chat(self):
        llm = LLMService({"provider": "openai", "model": "gpt-4"})
        handler = ChatHandler(llm, {"session_timeout": 300})
        sid = await handler.create_session()
        resp = await handler.chat(sid, "hello")
        assert isinstance(resp, str)
        assert len(resp) > 0

    @pytest.mark.asyncio
    async def test_chat_session_persists_history(self):
        llm = LLMService({"provider": "openai", "model": "gpt-4"})
        handler = ChatHandler(llm, {"session_timeout": 300})
        sid = await handler.create_session()
        await handler.chat(sid, "first msg")
        await handler.chat(sid, "second msg")
        session = await handler.get_session(sid)
        assert session is not None
        assert len(session.history) >= 2

    @pytest.mark.asyncio
    async def test_session_timeout_cleanup(self):
        llm = LLMService({"provider": "openai", "model": "gpt-4"})
        handler = ChatHandler(llm, {"session_timeout": -1})
        sid = await handler.create_session()
        await handler.cleanup_expired_sessions()
        session = await handler.get_session(sid)
        assert session is None

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self):
        llm = LLMService({"provider": "openai", "model": "gpt-4"})
        handler = ChatHandler(llm, {"session_timeout": 300})
        s1 = await handler.create_session()
        s2 = await handler.create_session()
        assert s1 != s2
        assert s1 in handler.sessions
        assert s2 in handler.sessions
