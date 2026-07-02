# Lumina — Virtual Human Framework

Lumina is a dual-stack virtual human / Live2D streaming framework:

- **lumina-py** (Python / FastAPI + gRPC) — Backend service: LLM orchestration, chat handling, TTS/STT, emotion system, sentiment analysis
- **lumina-cpp** (C++20 / CMake) — Frontend client: Live2D rendering, audio playback, camera capture, gRPC bridge
- **lumina-bridge** (Python) — Internal message bus between the gRPC servicer and backend modules

## Architecture

```
┌──────────────┐    gRPC    ┌──────────────────────┐
│  lumina-cpp  │◄─────────►│      lumina-py        │
│  (C++20)     │           │  (FastAPI + gRPC)     │
│  - Renderer  │           │  - ChatHandler        │
│  - Audio     │           │  - STT/TTS Engine     │
│  - Camera    │           │  - NeuroEngine        │
│  - Live2D    │           │  - Emotion System     │
└──────────────┘           └──────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │ lumina-bridge   │
                          │ (message bus)   │
                          └─────────────────┘
```

## Quick Start (Python backend only)

```bash
cd lumina-py
pip install -r requirements.txt
python -m src.main
```

Requires Python 3.10+.

## Building C++ frontend

```bash
cd lumina-cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Dependencies: CMake 3.20+, C++20 compiler, OpenGL, OpenAL, GLFW3, gRPC, Protobuf, Live2D Cubism SDK (optional).

## Project Status

| Layer | Status |
|-------|--------|
| Python backend | ✅ Production-ready (105 tests passing) |
| C++ frontend | ⚠️ Active development — renders stubs without Live2D SDK |
| gRPC bridge | ✅ Working |
| Live2D rendering | 🚧 Requires Cubism SDK |
| Real camera capture | ✅ Implemented (Windows DirectShow) |
| CI | ✅ Python lint + test on push/PR |

## License

Apache License 2.0 — see [LICENSE](LICENSE).
