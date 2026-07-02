import pytest
from chat_handler import ChatHandler
from llm_service import LLMService


@pytest.fixture
def chat_handler():
    llm = LLMService({"provider": "openai", "model": "gpt-4"})
    return ChatHandler(llm, {"session_timeout": 60, "max_sessions": 5})


@pytest.mark.asyncio
async def test_create_session(chat_handler):
    session_id = await chat_handler.create_session()
    assert session_id is not None
    assert session_id in chat_handler.sessions


@pytest.mark.asyncio
async def test_create_session_with_context(chat_handler):
    session_id = await chat_handler.create_session({"user": {"name": "TestUser"}})
    session = chat_handler.sessions[session_id]
    assert session.context["user"]["name"] == "TestUser"


@pytest.mark.asyncio
async def test_get_session(chat_handler):
    sid = await chat_handler.create_session()
    session = await chat_handler.get_session(sid)
    assert session is not None
    assert session.session_id == sid


@pytest.mark.asyncio
async def test_get_session_nonexistent(chat_handler):
    session = await chat_handler.get_session("nonexistent")
    assert session is None


@pytest.mark.asyncio
async def test_delete_session(chat_handler):
    sid = await chat_handler.create_session()
    await chat_handler.delete_session(sid)
    assert sid not in chat_handler.sessions


@pytest.mark.asyncio
async def test_add_message(chat_handler):
    sid = await chat_handler.create_session()
    await chat_handler.add_message(sid, "user", "hello")
    session = chat_handler.sessions[sid]
    assert len(session.history) == 1
    assert session.history[0]["role"] == "user"
    assert session.history[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_add_message_exceeds_max_history(chat_handler):
    sid = await chat_handler.create_session()
    session = chat_handler.sessions[sid]
    session.max_history = 3
    for i in range(5):
        await chat_handler.add_message(sid, "user", f"msg{i}")
    assert len(session.history) == 3
    assert session.history[-1]["content"] == "msg4"


@pytest.mark.asyncio
async def test_build_context_without_history(chat_handler):
    sid = await chat_handler.create_session()
    context = await chat_handler.build_context(sid, "test input")
    assert "[User]: test input" in context


@pytest.mark.asyncio
async def test_build_context_with_history(chat_handler):
    sid = await chat_handler.create_session()
    await chat_handler.add_message(sid, "user", "previous msg")
    await chat_handler.add_message(sid, "assistant", "previous reply")
    context = await chat_handler.build_context(sid, "new msg")
    assert "[User]: new msg" in context
    assert "previous msg" in context


@pytest.mark.asyncio
async def test_max_sessions_eviction(chat_handler):
    chat_handler.max_sessions = 2
    s1 = await chat_handler.create_session()
    s2 = await chat_handler.create_session()
    s3 = await chat_handler.create_session()
    assert len(chat_handler.sessions) <= 2
    assert s3 in chat_handler.sessions


@pytest.mark.asyncio
async def test_chat_with_mock(chat_handler):
    sid = await chat_handler.create_session()
    result = await chat_handler.chat(sid, "hi")
    assert result is not None
    assert len(result) > 0


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(chat_handler):
    chat_handler.session_timeout = -1
    sid = await chat_handler.create_session()
    await chat_handler.cleanup_expired_sessions()
    assert sid not in chat_handler.sessions


@pytest.mark.asyncio
async def test_add_message_with_metadata(chat_handler):
    sid = await chat_handler.create_session()
    await chat_handler.add_message(sid, "user", "hello", {"source": "test"})
    session = chat_handler.sessions[sid]
    assert session.history[0].get("metadata", {}).get("source") == "test"


    @pytest.mark.asyncio
    async def test_persona_prompt_in_context(chat_handler):
        chat_handler.persona_prompt = "You are a cat-girl VTuber named Nekoclaw."
        sid = await chat_handler.create_session()
        context = await chat_handler.build_context(sid, "pet pet")
        assert "cat-girl" in context or "Nekoclaw" in context

    @pytest.mark.asyncio
    async def test_persona_translate(chat_handler):
        chat_handler.persona_translate = lambda s: s.replace("hello", "nya~ hello")
        sid = await chat_handler.create_session()
        resp = await chat_handler.chat(sid, "say hello")
        assert "nya~" in resp

    @pytest.mark.asyncio
    async def test_persona_system_prompt_override(chat_handler):
        chat_handler.persona_prompt = "Persona: cat-girl"
        sid = await chat_handler.create_session()
        resp = await chat_handler.chat(sid, "hi", system_prompt="Override")
        session = await chat_handler.get_session(sid)
        assert session is not None
    chat_handler.persona_prompt = "You are a cat-girl VTuber named Nekoclaw."
    sid = await chat_handler.create_session()
    context = await chat_handler.build_context(sid, "pet pet")
    assert "cat-girl" in context or "Nekoclaw" in context
