# Changelog

## [0.2.0] — 2026-07-01

### Added
- End-to-end integration tests (REST API + core pipeline)
- C++ unit tests with Google Test (BridgeClient + gRPC stubs)
- GitHub Release automation (tag-triggered, Python wheel + source dist)
- `tests/test_integration.py` — 14 REST API endpoint tests
- `tests/test_core_pipeline.py` — 25 emotion/sentiment/chat pipeline tests
- `lumina-cpp/tests/` — Google Test framework + 20 C++ test cases
- `.github/workflows/release.yml` — version tag → CI → Release
- `CHANGELOG.md` — project changelog

### Changed
- CI pipeline expanded: 5 jobs (python + proto + cpp + cpp-test + status)
- `Makefile` — new `cpp-test` target (FetchContent + Google Test)
- `scripts/ci-make-proto.sh` — ensure `grpc_cpp_plugin` findable

### Fixed
- `sentiment.py` — `set.lower()` AttributeError on Python 3.14

---

## [0.1.0] — 2026-06-30

### Added
- Mock mode as first-class citizen (`mock_providers.py`)
- Sentiment analysis engine (`sentiment.py`)
- gRPC retry/degradation wrapper (`grpc_retry.py`)
- Config validation with pydantic (`config_schema.py`)
- AgentInterface Protocol for dependency injection (`interfaces.py`)
- Bridge restructure: `lumina-bridge` split into `bus/` + `grpc/`
- Proactive behavior in NeuroEngine (`_proactive_loop`)
- One-click launcher (`start.py`)
- Docker support (`Dockerfile` + `docker-compose.yml`)
- Client examples (`python_client.py`, `js_client.js`, `browser_demo.py`)
- CI configuration (GitHub Actions — lint + test + proto + C++ build)
- C++ minimal build verification (`LUMINA_BUILD_GRPC_ONLY`)
- Dedicated IO thread pool (`thread_pool.py`)
- Prometheus-format `/metrics` endpoint (`metrics.py`)
- `@_grpc_handler` decorator to eliminate repeated error handling
- PowerShell launcher (`start.ps1`)
- Architecture/Contributing/Roadmap docs
- 42+ unit tests (emotion_system, sentiment, chat_handler, neuro_engine)
- Multi-role README with Mock Mode badge and feature table
- Cross-field config validation (`@model_validator`)
- `_check_proto()` caching (class-level flag)

### Fixed
- C++ compilation: `#ifdef _WIN32` concatenation, missing `#include <memory>`
- gRPC server: bridge=None guards, CancelledError handling, Windows signal
- Emotion system: `_normalize()` after blend/decay, neutral decay independence
- NeuroEngine: GOODBYE→IDLE state transition guards
- STT engine: `Optional[int]` type hint
- All C++ files formatted from single-line corruption to K&R style
- CORS: `allow_credentials=False` with `allow_origins=["*"]`
- `start.py`: `--open-browser` skipped in mock mode

### Changed
- `server.py` → pure service class; `main.py` → FastAPI + uvicorn launcher
- `neuro_engine.py` → `match/case` event dispatch, `AgentInterface` parameter
- `stt_engine.py` → `match/case` for audio format + engine dispatch
- `chat_handler.py` → heap-based session expiry, list+join for streaming
- `emotion_system.py` → manual max, multiplication normalize, frozenset
- CMakeLists.txt → `find_package(QUIET)` + conditional compilation
- CrewManager → dedicated IO thread pool (not default)
