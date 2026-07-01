# Project Genesis: Lumina

虚拟人全栈平台 — 基于 N.E.K.O + CrewAI + Neuro-simulator 重构的高性能 Live2D/VRM 虚拟人系统。

## 架构

```
lumina/
├── lumina-proto/    # gRPC 协议定义 (Proto3)
├── lumina-cpp/      # C++ 前端 (渲染/音视频/交互)
│   ├── src/        #  主程序源码
│   ├── include/    #  头文件
│   └── external/   #  第三方 (Live2D, GLFW)
├── lumina-py/       # Python 后端 (AI/Agent/TTS)
│   └── src/        #  服务端源码
└── lumina-bridge/   # IPC 通信桥接层
```

## 通信流程

```
[C++ Client] ←→ gRPC/IPC ←→ [Python Backend]
     │                            │
  (Live2D/VRM)               (CrewAI Agents)
  (Audio I/O)                (Neuro-simulator)
  (User Input)               (LLM / TTS / STT)
```

## 构建

### C++
```bash
cd lumina-cpp
cmake -B build
cmake --build build
```

### Python
```bash
cd lumina-py
pip install -r requirements.txt
python -m src.server
```
