# Contributing to Lumina

## Project Structure

```
lumina-py/          Python backend (FastAPI + gRPC)
lumina-cpp/         C++ frontend (CMake + C++20)
lumina-bridge/      Internal message bus
lumina-proto/       Protocol Buffers definitions (separate)
```

## Python Development

```bash
cd lumina-py
pip install -e ".[dev]"
python -m pytest tests/ -v
flake8 src/ --max-line-length=120
```

## C++ Development

### Prerequisites
- CMake 3.20+
- C++20 compiler (GCC 11+, Clang 14+, MSVC 2022+)
- gRPC and Protobuf (for bridge client)
- GLFW3 + OpenAL (for frontend renderer)
- Live2D Cubism SDK (optional, for Live2D rendering)

### Build

```bash
cd lumina-cpp
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
ctest --test-dir build
```

### Platform-specific build

```bash
# Minimal gRPC-only build (CI)
cmake -B build -DLUMINA_BUILD_GRPC_ONLY=ON
cmake --build build
```

## Code Style

### C++
- `#pragma once` for headers
- `namespace lumina { ... } // namespace lumina`
- Braces on same line as function/control flow
- 4-space indentation
- PIMPL idiom for implementation hiding
- No exceptions — use `bool` return + error logging
- No raw `new`/`delete` — use `std::unique_ptr`/`std::shared_ptr`

### Python
- Type hints on all function signatures
- `logging` module (not `print`)
- Async/await for I/O operations
- Dataclasses for data containers

## Testing

- **Python**: `pytest` in `lumina-py/tests/`
- **C++**: Google Test in `lumina-cpp/tests/`

Before submitting a PR, ensure:
1. Python tests pass
2. Flake8 reports no new warnings
3. C++ core tests pass (if build environment available)
