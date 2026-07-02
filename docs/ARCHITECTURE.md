# Lumina — Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     HTTP/REST (8000)                     │
│   FastAPI ←→ Chat/TTS/STT/Live endpoints               │
├─────────────────────────────────────────────────────────┤
│                     gRPC (50051)                         │
│   C++ Client ←→ LuminaVirtualHumanServicer              │
├─────────────────────────────────────────────────────────┤
│                     Event Bus (IPC)                      │
│   BridgeServer (pub/sub) ←→ Python Modules              │
└─────────────────────────────────────────────────────────┘
```

## Layer Overview

### 1. API Layer (`lumina-py/src/api_routes.py`)
FastAPI REST endpoints for LLM chat, TTS, STT, and live simulation.

| Endpoint | Function | Mock Support |
|----------|----------|-------------|
| `POST /api/v1/chat` | Process chat message | MockLLM returns canned |
| `POST /api/v1/chat/stream` | SSE streaming chat | MockLLM char-by-char |
| `POST /api/v1/tts` | Text-to-speech | MockTTS returns silence |
| `POST /api/v1/stt` | Speech-to-text | MockSTT returns random |
| `POST /api/v1/live/start` | Start neuro simulation | Full mock flow |
| `POST /api/v1/live/stop` | Stop neuro simulation | — |
| `GET /api/v1/status` | Full system status | Includes mock flag |

### 2. Service Layer

```
LLMService / MockLLM      ← chat responses (OpenAI / canned)
   │
ChatHandler               ← session management, context
   │
EmotionSystem              ← multi-dimensional emotion vector
SentimentAnalyzer          ← NLP-based text emotion detection
   │
TTSEngine / MockTTS        ← voice synthesis (edge-tts / silence)
STTEngine / MockSTT        ← voice recognition (whisper / vosk)
   │
NeuroEngine               ← live stream simulation
   ├── Viewer simulation (danmaku/gift/follow)
   ├── State machine (IDLE→WARMUP→INTERACTION→...)
   └── Proactive behavior (spontaneous utterances)
   │
CrewManager               ← CrewAI agent orchestration
```

### 3. Mock System

When `mock.enabled=true` or `openai` is not installed:

```
MockLLM    ── keyword matching + random responses
MockTTS    ── zero-filled PCM audio + estimated phonemes
MockSTT    ── random transcription output
MockLipSync ── sin-wave mouth shapes
```

All mock providers respect `mock.latency` to simulate realistic timing.

### 4. gRPC Layer (`lumina-bridge/src/grpc_server.py`)

Bridges C++ frontend ↔ Python backend via gRPC unary/streaming RPCs.

- **Retry**: `GrpcRetryWrapper` implements exponential backoff (3 retries, 2x factor)
- **Degradation**: Each RPC has a fallback handler when proto stubs are absent
- **Graceful shutdown**: `serve_grpc()` returns early when `_HAS_PROTO` is False

### 5. State Machine (`NeuroEngine`)

```
IDLE → WARMUP → INTERACTION ⇄ PERFORMANCE → GOODBYE → IDLE
       │           │              │
   (greeting)   (chatting)    (singing/dancing)
```

Proactive utterances fire every `proactive_interval` (default: 30s).

---

## Data Flow: Chat Request

```
User → POST /api/v1/chat
  → api_routes.py
    → ChatHandler.process_message()
      → SentimentAnalyzer.analyze(text)   ← detect emotion
      → EmotionSystem.blend_emotion()      ← update internal state
      → LLMService.chat(prompt + context)  ← get response
      → (optional) TTSEngine.synthesize()  ← generate audio
      → (optional) LipSyncGenerator        ← generate visemes
  ← JSON { text, emotion, audio?, visemes? }
```

---

## Key Design Decisions

1. **Mock as first-class mode** — not just a fallback. New contributors can explore the full API surface without any paid services.

2. **Auto-detection of available services** — `server.py` checks `import openai`, `import whisper`, etc. at startup and configures providers accordingly.

3. **Event bus for loose coupling** — `BridgeServer` uses pub/sub to decouple gRPC events from AI processing.

4. **Windows signal handling** — `asyncio` event loop with `try/except KeyboardInterrupt` instead of `add_signal_handler`.
