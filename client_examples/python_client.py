"""
Lumina Python Client — Example Usage

Demonstrates how to interact with Lumina's REST API from Python.
"""
import json
import requests

BASE_URL = "http://localhost:8000"


def health_check() -> dict:
    resp = requests.get(f"{BASE_URL}/health")
    resp.raise_for_status()
    return resp.json()


def send_chat(message: str, session_id: str = None) -> dict:
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    resp = requests.post(f"{BASE_URL}/api/v1/chat", json=payload)
    resp.raise_for_status()
    return resp.json()


def stream_chat(message: str):
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/stream",
        json={"message": message},
        stream=True,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                yield decoded[6:]


def synthesize_speech(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    resp = requests.post(
        f"{BASE_URL}/api/v1/tts",
        json={"text": text, "voice": voice},
    )
    resp.raise_for_status()
    return resp.content


def transcribe_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/v1/stt",
            files={"file": f},
        )
    resp.raise_for_status()
    return resp.json().get("text", "")


def get_status() -> dict:
    resp = requests.get(f"{BASE_URL}/api/v1/status")
    resp.raise_for_status()
    return resp.json()


def start_live() -> dict:
    resp = requests.post(f"{BASE_URL}/api/v1/live/start")
    resp.raise_for_status()
    return resp.json()


def stop_live() -> dict:
    resp = requests.post(f"{BASE_URL}/api/v1/live/stop")
    resp.raise_for_status()
    return resp.json()


# ── Demo ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("Lumina Health:", health_check())

    print("\n--- Chat ---")
    result = send_chat("你好！")
    print(f"  Response: {result['response']}")
    print(f"  Emotion: {result.get('emotion')}")

    print("\n--- Stream Chat ---")
    print("  ", end="", flush=True)
    for token in stream_chat("今天天气怎么样？"):
        print(token, end="", flush=True)
    print()

    print("\n--- Status ---")
    status = get_status()
    print(f"  Mock mode: {status.get('mock_mode', 'N/A')}")
    print(f"  Uptime: {status.get('uptime', 0):.1f}s")
