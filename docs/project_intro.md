# Lumina — Virtual Human Live Streaming Platform

Lumina 是一个全栈虚拟人直播平台，结合 **C++ 前端渲染引擎** 与 **Python AI 后端**，通过 gRPC 协议实现高性能通信。支持 Live2D/VRM 模型驱动、实时语音交互、情感识别、弹幕互动等能力。

---

## 整体架构

```
lumina/
├── lumina-proto/       # gRPC 协议定义 (Proto3)
│   └── src/lumina.proto
├── lumina-cpp/         # C++ 前端 (渲染/音视频/交互)
│   ├── src/            # 主程序源码
│   ├── include/        # 头文件
│   └── CMakeLists.txt
├── lumina-py/          # Python 后端 (AI/Agent/TTS/STT)
│   ├── src/            # 服务端源码
│   ├── tests/          # 单元测试
│   ├── config.yaml     # 配置文件
│   └── pyproject.toml  # 项目元数据
└── lumina-bridge/      # IPC 通信桥接层
    ├── src/            # gRPC 服务端 + 事件总线
    └── include/        # C++ IPC 通道接口
```

### 通信流程

```
[C++ Client] ←→ gRPC/IPC ←→ [Python Backend]
     │                            │
  (Live2D/VRM)               (CrewAI Agents)
  (Audio I/O)                (Neuro-simulator)
  (User Input)               (LLM / TTS / STT)
```

---

## 核心模块

### 1. lumina-py (Python AI 后端)

| 模块 | 功能 |
|------|------|
| `LLMService` | 大语言模型对话 (OpenAI / mock) |
| `ChatHandler` | 会话管理、上下文构建、情绪标签解析 |
| `EmotionSystem` | 多维情绪向量、衰减、融合 |
| `TTSEngine` | 文本转语音 (edge-tts / OpenAI / pyttsx3) + 缓存 |
| `STTEngine` | 语音转文字 (whisper / faster-whisper / vosk) + VAD |
| `LipSyncGenerator` | 口型同步数据生成 (文本/音频/音素) |
| `NeuroEngine` | 直播模拟引擎 (弹幕/礼物/follow 模拟 + 状态机) |
| `CrewManager` | CrewAI Agent 编排 (聊天/直播/规划) |
| `AudioUtils` | 音频编解码、混音、归一化、缓存 |
| `api_routes.py` | FastAPI REST API (chat/tts/stt/status/live) |
| `server.py` | LuminaServer 主入口 + gRPC 启动 |
| `main.py` | 应用启动入口 (FastAPI + gRPC + 优雅关闭) |

### 2. lumina-cpp (C++ 前端)

| 模块 | 功能 |
|------|------|
| `Renderer` | OpenGL 渲染循环、模型管理 |
| `Live2DModel` | Live2D 模型加载/更新/渲染 |
| `AudioEngine` | OpenAL 音频播放/录制 |
| `InputHandler` | 键盘/鼠标输入、摄像头捕获 |
| `LipSyncHandler` | 口型同步播放/插值 |
| `BridgeClient` | gRPC 客户端 (Chat/Audio/Live2D) |

### 3. lumina-proto (gRPC 协议)

定义 `VirtualHuman` 服务，包含 11 个 RPC：

- `ProcessChat` — 对话处理
- `StreamAudio` — 语音流式合成
- `SyncLip` — 口型同步
- `TriggerAction` — 动作触发
- `SendEmotion` — 情绪控制
- `Live2DControl` — Live2D 参数控制
- `StreamStatus` — 状态推送
- `StreamLiveStatus` — 直播状态推送
- `SendGift` — 礼物通知
- `ProcessAudioStream` — 音频流式识别

### 4. lumina-bridge (通信桥接)

- `BridgeServer` — 进程内事件总线 (发布/订阅模式)
- `LuminaVirtualHumanServicer` — gRPC 服务端 (桥接 Python 后端与 C++ 前端)
- `IpcChannel` — C++ IPC 通道抽象

---

## 快速开始

### Python 后端

```bash
cd lumina-py
pip install -r requirements.txt
python -m src.main
```

**REST API 端点**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/chat` | 对话处理 |
| POST | `/api/v1/chat/stream` | 流式对话 (SSE) |
| POST | `/api/v1/tts` | 语音合成 |
| POST | `/api/v1/stt` | 语音识别 |
| POST | `/api/v1/live/start` | 开启直播模拟 |
| POST | `/api/v1/live/stop` | 停止直播模拟 |
| GET | `/api/v1/status` | 服务状态 |

### C++ 前端

```bash
cd lumina-cpp
cmake -B build
cmake --build build
./build/lumina_client
```

### 编译 Protocol Buffers

```bash
cd lumina-proto
build_proto.bat
```

---

## API 示例

```bash
# 对话请求
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好！"}'

# 响应
{
  "session_id": "abc-123",
  "response": "你好呀！今天想聊点什么？",
  "emotion": "happy",
  "suggested_action": "wave"
}
```

---

## 配置说明

参见 `lumina-py/config.yaml`，支持：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `llm.provider` | LLM 提供商 | `openai` |
| `llm.model` | 模型名称 | `gpt-4` |
| `tts.engine` | TTS 引擎 | `edge-tts` |
| `tts.voice` | 发音人 | `zh-CN-XiaoxiaoNeural` |
| `stt.engine` | STT 引擎 | `whisper` |
| `stt.model` | STT 模型大小 | `base` |
| `neuro.audience_size` | 模拟观众数量 | `10` |
| `chat.session_timeout` | 会话超时(秒) | `300` |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 协议 | Protocol Buffers (Proto3), gRPC |
| AI 后端 | Python 3.10+, FastAPI, OpenAI API, CrewAI |
| 渲染前端 | C++20, OpenGL, OpenAL, Live2D Cubism SDK |
| 语音 | edge-tts, OpenAI TTS, Whisper, Vosk |
| 通信 | gRPC (异步), HTTP/2 Server-Sent Events |
| 测试 | pytest, pytest-asyncio |

---

## 注意事项

1. **C++ 编译依赖**: OpenGL、OpenAL、gRPC、Protobuf、GLFW3 需预先安装
2. **Live2D SDK**: 将 Live2D Cubism SDK 放置于 `lumina-cpp/external/live2d-cubism/`
3. **STT 模型**: `openai-whisper` 或 `vosk` 模型首次使用会自动下载
4. **gRPC 编译**: 启动前需运行 `build_proto.bat` 生成 Python/C++ 桩代码
5. **Windows 兼容**: 信号处理已适配 Windows (Ctrl+C 关闭), 未使用 `add_signal_handler`
