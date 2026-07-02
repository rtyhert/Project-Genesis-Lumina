import asyncio
import pytest
from neuro_engine import NeuroEngine, StreamState, LiveEvent


class MockAgent:
    async def run_task_async(self, task_description, agent_name="chat"):
        return f"Mock response to: {task_description[:30]}"

    async def generate_stream_script(self, context):
        class MockScript:
            lines = ["Hello everyone!", "Welcome to the stream!", "Let's have fun today!"]
        return MockScript()

    async def chat_with_emotion(self, user_input, history=None):
        class MockChatOutput:
            response = "Mock reply"
            emotion = "neutral"
            action = None
        return MockChatOutput()


@pytest.fixture
def neuro():
    config = {"audience_size": 5, "auto_reply": True, "proactive_interval": 300}
    return NeuroEngine(config, MockAgent())


class TestNeuroEngine:
    def test_initial_state(self, neuro):
        assert neuro.state == StreamState.IDLE
        assert neuro.active is False

    def test_viewers_loaded(self, neuro):
        assert len(neuro.viewers) == 5

    def test_proactive_templates_loaded(self, neuro):
        assert len(neuro.proactive_templates) > 0

    def test_gift_table_loaded(self, neuro):
        assert len(neuro.gift_table) > 0
        assert len(neuro.gift_names) > 0

    def test_state_durations_loaded(self, neuro):
        assert len(neuro.state_durations) > 0

    @pytest.mark.asyncio
    async def test_initial_followers_zero(self, neuro):
        status = await neuro.get_status()
        assert status["followers"] == 0
        assert status["total_gifts"] == 0
        assert status["total_messages"] == 0

    @pytest.mark.asyncio
    async def test_average_mood_computation(self, neuro):
        status = await neuro.get_status()
        assert 0 <= status["average_mood"] <= 1

    @pytest.mark.asyncio
    async def test_get_status_when_idle(self, neuro):
        status = await neuro.get_status()
        assert status["active"] is False
        assert status["state"] == "idle"
        assert status["viewer_count"] == 5
        assert status["event_queue_size"] == 0

    @pytest.mark.asyncio
    async def test_start(self, neuro):
        await neuro.start()
        assert neuro.active is True
        assert neuro.state == StreamState.WARMUP
        status = await neuro.get_status()
        assert status["active"] is True
        assert status["state"] == "warmup"
        await neuro.stop()

    @pytest.mark.asyncio
    async def test_stop_when_running(self, neuro):
        await neuro.start()
        assert neuro.active is True
        await neuro.stop()
        assert neuro.active is False
        assert neuro.state == StreamState.IDLE
        status = await neuro.get_status()
        assert status["active"] is False
        assert status["state"] == "idle"

    @pytest.mark.asyncio
    async def test_double_start(self, neuro):
        await neuro.start()
        await neuro.start()  # second start should be no-op
        assert neuro.active is True
        await neuro.stop()

    @pytest.mark.asyncio
    async def test_stop_when_idle(self, neuro):
        await neuro.stop()  # stopping when idle should not raise
        assert neuro.active is False
        assert neuro.state == StreamState.IDLE

    @pytest.mark.asyncio
    async def test_start_stop_multiple_cycles(self, neuro):
        for _ in range(3):
            await neuro.start()
            assert neuro.active is True
            await asyncio.sleep(0.05)
            await neuro.stop()
            assert neuro.active is False
        status = await neuro.get_status()
        assert status["active"] is False

    @pytest.mark.asyncio
    async def test_events_queue_cleared_after_stop(self, neuro):
        await neuro.start()
        neuro.event_queue.put_nowait(LiveEvent(type="danmaku", viewer="Test"))
        await asyncio.sleep(0.1)
        await neuro.stop()
        status = await neuro.get_status()
        assert status["event_queue_size"] == 0
