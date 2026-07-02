"""End-to-end integration tests — REST API + core pipeline."""
import pytest
import json
from unittest.mock import AsyncMock, patch


@pytest.fixture
def app():
    from fastapi.testclient import TestClient
    from main import create_app
    from server import LuminaServer
    import os, pathlib

    config_path = pathlib.Path(__file__).resolve().parent.parent / "config.yaml"
    server = LuminaServer(str(config_path))
    app = create_app(server)
    return TestClient(app)


class TestRESTEndpoints:
    def test_health(self, app):
        resp = app.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "mock_mode" in data
        assert "uptime" in data

    def test_metrics_endpoint(self, app):
        resp = app.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "lumina_requests_total" in text
        assert "lumina_errors_total" in text
        assert "lumina_latency_seconds" in text

    def test_chat_endpoint(self, app):
        resp = app.post("/api/v1/chat", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "response" in data
        assert "emotion" in data

    def test_chat_with_session(self, app):
        resp1 = app.post("/api/v1/chat", json={"message": "你好"})
        sid = resp1.json()["session_id"]
        resp2 = app.post("/api/v1/chat", json={"session_id": sid, "message": "今天天气怎么样"})
        assert resp2.status_code == 200
        assert resp2.json()["session_id"] == sid

    def test_chat_empty_message_rejected(self, app):
        resp = app.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_chat_stream_sse(self, app):
        from httpx import AsyncClient, ASGITransport
        import asyncio
        async def do_stream():
            transport = ASGITransport(app=app.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                async with client.stream("POST", "/api/v1/chat/stream", json={"message": "你好"}) as resp:
                    assert resp.status_code == 200
                    content = ""
                    async for chunk in resp.aiter_text():
                        content += chunk
                        break
                    assert "data:" in content or "Hello" in content
        asyncio.run(do_stream())

    def test_status_endpoint(self, app):
        resp = app.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "mock_mode" in data
        assert "live_active" in data
        assert "session_count" in data

    def test_live_start_stop(self, app):
        start = app.post("/api/v1/live/start")
        assert start.status_code == 200
        assert start.json()["success"]

        status = app.get("/api/v1/live/status")
        assert status.status_code == 200

        stop = app.post("/api/v1/live/stop")
        assert stop.status_code == 200

    def test_tts_endpoint(self, app):
        resp = app.post("/api/v1/tts", json={"text": "你好世界"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert len(resp.content) > 0

    def test_stt_endpoint(self, app):
        import base64
        audio_b64 = base64.b64encode(b"\x00\x00" * 16000).decode()
        resp = app.post("/api/v1/stt", json={"audio_base64": audio_b64})
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data

    def test_404(self, app):
        resp = app.get("/nonexistent")
        assert resp.status_code == 404

    def test_cors_headers(self, app):
        resp = app.options("/api/v1/chat", headers={"Origin": "http://example.com"})
        assert resp.headers.get("access-control-allow-origin") == "*"


class TestCorePipeline:
    def test_chat_to_emotion_pipeline(self, app):
        chat = app.post("/api/v1/chat", json={"message": "今天真的好开心！"})
        assert chat.status_code == 200
        data = chat.json()
        assert data["emotion"] in ("happy", "neutral")

    def test_chat_handler_session_cleanup(self, app):
        for i in range(5):
            app.post("/api/v1/chat", json={"message": f"test{i}"})
        status = app.get("/api/v1/status")
        assert status.json()["session_count"] <= 1000

    def test_concurrent_chat_sessions(self, app):
        import asyncio
        from httpx import AsyncClient, ASGITransport

        async def send_chat(msg):
            transport = ASGITransport(app=app.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/chat", json={"message": msg})
                return resp.status_code

        async def run():
            tasks = [send_chat(f"msg{i}") for i in range(5)]
            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.run(run())
        assert all(r == 200 for r in results)
