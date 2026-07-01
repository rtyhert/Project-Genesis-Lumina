# uPage - Virtual Human Full-Stack Platform

基于 N.E.K.O + CrewAI + Neuro-simulator 重构的全栈虚拟人平台。

## 架构

```
upage/
├── upage-proto/    # gRPC 协议定义 (Proto3)
├── upage-cpp/      # C++ 前端 (渲染/音视频/交互)
│   ├── src/        #  主程序源码
│   ├── include/    #  头文件
│   └── external/   #  第三方 (Live2D, GLFW)
├── upage-py/       # Python 后端 (AI/Agent/TTS)
│   └── src/        #  服务端源码
└── upage-bridge/   # IPC 通信桥接层
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
cd upage-cpp
cmake -B build
cmake --build build
```

### Python
```bash
cd upage-py
pip install -r requirements.txt
python -m src.server
```
