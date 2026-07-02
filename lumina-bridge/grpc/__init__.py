"""lumina-bridge.grpc — gRPC servicer for VirtualHuman service."""
from __future__ import annotations

import asyncio
import functools
import grpc
import logging
import time
import sys
from typing import AsyncIterator, Callable, TypeVar
from pathlib import Path

from lumina_bridge.bus import BridgeServer, BridgeMessage

F = TypeVar("F", bound=Callable)


def _grpc_handler(method: F) -> F:
    @functools.wraps(method)
    async def wrapper(self, request, context, *args, **kwargs):
        try:
            if not _HAS_PROTO:
                raise RuntimeError(
                    "gRPC proto stubs not compiled; run lumina-proto/build_proto.bat"
                )
            return await method(self, request, context, *args, **kwargs)
        except RuntimeError:
            raise
        except Exception as e:
            log.error("%s failed: %s", method.__name__, e, exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return _default_reply(method.__name__)

    return wrapper


_DEFAULT_REPLIES = {}


def _default_reply(method_name: str):
    import importlib
    if method_name not in _DEFAULT_REPLIES:
        m = importlib.import_module("lumina_pb2")
        _DEFAULT_REPLIES[method_name] = m
    pb2 = _DEFAULT_REPLIES[method_name]
    if method_name == "ProcessChat":
        return pb2.ChatResponse(reply_text="[System] 抱歉，我暂时无法回复")
    if method_name == "StreamAudio":
        return pb2.AudioChunk(data=b"", is_final=True, sequence=0)
    if method_name == "ProcessAudioStream":
        return pb2.STTResult(text="", confidence=0.0, is_final=True, language="zh")
    if method_name == "SyncLip":
        return pb2.LipSyncData()
    if method_name == "TriggerAction":
        return pb2.ActionResponse(success=False, error_message="internal error")
    if method_name == "SendEmotion":
        return pb2.EmotionResponse(success=False)
    if method_name == "Live2DControl":
        return pb2.Live2DResponse(success=False, error="internal error")
    if method_name == "SendGift":
        return pb2.GiftResponse(success=False)
    return None

_proto_path = str(Path(__file__).resolve().parent.parent.parent / "lumina-proto" / "build")
if _proto_path not in sys.path:
    sys.path.insert(0, _proto_path)

_HAS_PROTO = False
pb2 = None
pb2_grpc = None

try:
    import lumina_pb2 as pb2
    import lumina_pb2_grpc as pb2_grpc
    _HAS_PROTO = True
except ImportError:
    pass

log = logging.getLogger("lumina.bridge.grpc")


class LuminaVirtualHumanServicer:
    def __init__(self, bridge: BridgeServer = None,
                 tts=None, stt=None, neuro=None, crew_manager=None):
        self.bridge = bridge
        self.tts = tts
        self.stt = stt
        self.neuro = neuro
        self.crew_manager = crew_manager
        self.active_streams: dict[str, asyncio.Queue] = {}
        self.emotion_history: dict[str, list] = {}
        self._neuro_refcount: int = 0
        if not _HAS_PROTO:
            log.warning("gRPC servicer created without proto stubs; RPCs will fail")

    @_grpc_handler
    async def ProcessChat(self, request, context) -> pb2.ChatResponse:
        log.info(f"ProcessChat: user={request.user_id} msg={request.message[:60]}")
        if self.bridge is None:
            return pb2.ChatResponse(reply_text="[System] Bridge not available")
        msg = BridgeMessage(
            msg_type="chat_request",
            payload=request.message,
            topic=f"user/{request.user_id}/{request.session_id}",
            timestamp=time.time(),
        )
        result = await self.bridge.dispatch(msg)
        if result:
            resp = pb2.ChatResponse()
            resp.reply_text = result.payload
            if hasattr(result, "topic") and result.topic:
                parts = result.topic.split("|")
                if len(parts) >= 2:
                    resp.emotion_tag.category = getattr(
                        pb2.EmotionCategory, parts[0].upper(), pb2.EmotionCategory.NEUTRAL
                    )
                    resp.action_tag = parts[1]
            return resp
        return pb2.ChatResponse(reply_text="[System] 抱歉，我暂时无法回复")

    async def StreamAudio(self, request, context) -> AsyncIterator[pb2.AudioChunk]:
        log.info(f"StreamAudio: text={request.text[:40]} voice={request.voice_id}")
        tts = self.tts
        if tts is None:
            from lumina_py.src.tts_engine import TTSEngine
            tts = TTSEngine({
                "engine": "edge-tts",
                "voice": request.voice_id or "zh-CN-XiaoxiaoNeural",
                "speed": request.speed or 1.0,
            })
        seq = 0
        async for data in tts.synthesize(request.text):
            yield pb2.AudioChunk(data=data, timestamp=int(time.time() * 1000), is_final=False, sequence=seq)
            seq += 1
        yield pb2.AudioChunk(data=b"", timestamp=int(time.time() * 1000), is_final=True, sequence=seq)

    @_grpc_handler
    async def ProcessAudioStream(self, request_iterator, context) -> pb2.STTResult:
        log.info("ProcessAudioStream: receiving audio stream")
        audio_buffer = bytearray()
        async for chunk in request_iterator:
            audio_buffer.extend(chunk.data)
            if chunk.session_id:
                pass
            if chunk.is_final:
                break
        stt = self.stt
        if stt is None:
            from lumina_py.src.stt_engine import STTEngine
            stt = STTEngine({"engine": "whisper", "model": "base"})
        text = await stt.transcribe(bytes(audio_buffer))
        return pb2.STTResult(text=text or "", confidence=0.85, is_final=True, language="zh")

    @_grpc_handler
    async def SyncLip(self, request, context) -> pb2.LipSyncData:
        log.info(f"SyncLip: text={request.text[:40]}")
        if self.bridge is None:
            return pb2.LipSyncData()
        msg = BridgeMessage(msg_type="lip_sync", payload=request.text, topic=request.language, timestamp=time.time())
        result = await self.bridge.dispatch(msg)
        frames = []
        duration = 0.0
        if result and result.payload:
            import json
            try:
                data = json.loads(result.payload)
                for f in data.get("frames", []):
                    frames.append(pb2.LipFrame(
                        time=f.get("t", 0.0), mouth_open=f.get("mo", 0.0),
                        jaw_y=f.get("jy", 0.0), tongue_x=f.get("tx", 0.0),
                        tongue_y=f.get("ty", 0.0), lip_width=f.get("lw", 0.0),
                    ))
                duration = data.get("duration", 0.0)
            except json.JSONDecodeError:
                pass
        return pb2.LipSyncData(frames=frames, total_duration=duration)

    @_grpc_handler
    async def TriggerAction(self, request, context) -> pb2.ActionResponse:
        log.info(f"TriggerAction: type={request.action_type} emotion={request.emotion}")
        if self.bridge is None:
            return pb2.ActionResponse(success=True, animation_id=request.action_type, duration=1.0)
        msg = BridgeMessage(
            msg_type="action_trigger",
            payload=f"{request.action_type}|{request.emotion}|{request.intensity}",
            timestamp=time.time(),
        )
        result = await self.bridge.dispatch(msg)
        if result and result.payload:
            return pb2.ActionResponse(success=True, animation_id=result.payload, duration=request.intensity * 2.0)
        return pb2.ActionResponse(success=True, animation_id=request.action_type, duration=1.0)

    @_grpc_handler
    async def SendEmotion(self, request, context) -> pb2.EmotionResponse:
        log.info(f"SendEmotion: session={request.session_id} cat={request.emotion.category}")
        tag = request.emotion
        if request.session_id not in self.emotion_history:
            self.emotion_history[request.session_id] = []
        self.emotion_history[request.session_id].append(tag)
        msg = BridgeMessage(
            msg_type="emotion",
            payload=f"{tag.category}|{tag.intensity}|{tag.valence}|{tag.arousal}",
            topic=request.session_id,
            timestamp=time.time(),
        )
        if self.bridge:
            await self.bridge.dispatch(msg)
        match tag.category:
            case pb2.EmotionCategory.HAPPY:
                transition = "happy"
            case pb2.EmotionCategory.SAD:
                transition = "sad"
            case pb2.EmotionCategory.ANGRY:
                transition = "angry"
            case _:
                transition = "idle"
        return pb2.EmotionResponse(success=True, resulting_emotion=tag, transition_animation=transition)

    @_grpc_handler
    async def Live2DControl(self, request, context) -> pb2.Live2DResponse:
        log.info(f"Live2DControl: session={request.session_id}")
        if self.bridge is None:
            return pb2.Live2DResponse(success=True, animation_id="anim_default", transition_duration=request.transition_time)
        cmd_type = request.WhichOneof("command")
        payload = f"{cmd_type}|{request.transition_time}|{request.queue}|{request.priority}"
        match cmd_type:
            case "expression":
                ctrl = request.expression
                payload += f"|{ctrl.type}|{ctrl.intensity}|{ctrl.duration}"
            case "motion":
                ctrl = request.motion
                payload += f"|{ctrl.group}|{ctrl.animation_id}|{ctrl.speed}|{ctrl.loop}"
            case "param":
                ctrl = request.param
                payload += f"|{ctrl.param_name}|{ctrl.value}"
            case "lip_sync":
                ctrl = request.lip_sync
                payload += f"|{ctrl.enabled}|{ctrl.gain}"
            case "physics":
                ctrl = request.physics
                payload += f"|{ctrl.enabled}|{ctrl.reset}"
        msg = BridgeMessage(msg_type="live2d", payload=payload, topic=request.session_id, timestamp=time.time())
        result = await self.bridge.dispatch(msg)
        anim_id = result.payload if result and result.payload else "anim_default"
        return pb2.Live2DResponse(success=True, animation_id=anim_id, transition_duration=request.transition_time)

    async def StreamStatus(self, request, context) -> AsyncIterator[pb2.StatusEvent]:
        log.info(f"StreamStatus: client={request.client_id} events={request.subscribed_events}")
        queue: asyncio.Queue = asyncio.Queue()
        self.active_streams[request.client_id] = queue
        try:
            while True:
                if context.cancelled():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield pb2.StatusEvent(
                        event_type=payload.get("type", "heartbeat"),
                        payload=payload.get("data", ""),
                        timestamp=int(time.time() * 1000),
                    )
                except asyncio.TimeoutError:
                    yield pb2.StatusEvent(event_type="heartbeat", payload="", timestamp=int(time.time() * 1000))
        finally:
            self.active_streams.pop(request.client_id, None)
            log.info(f"StreamStatus: client {request.client_id} disconnected")

    async def StreamLiveStatus(self, request, context) -> AsyncIterator[pb2.LiveStatusEvent]:
        log.info(f"StreamLiveStatus: stream={request.stream_id} platform={request.platform}")
        neuro = self.neuro
        if neuro is None:
            log.warning("No NeuroEngine available for live streaming")
            return
        self._neuro_refcount += 1
        if not neuro.active:
            await neuro.start()
        try:
            while not context.cancelled():
                status = await neuro.get_status()
                event = pb2.LiveStatusEvent(
                    stream_id=request.stream_id,
                    event_type=pb2.LiveEventType.AUDIENCE_MESSAGE,
                    timestamp=int(time.time() * 1000),
                    event_id=int(time.time() * 1000000),
                )
                event.audience_msg.message = f"Viewers: {status['viewer_count']}, State: {status['state']}"
                yield event
                await asyncio.sleep(3.0)
        finally:
            self._neuro_refcount -= 1
            if neuro.active and self._neuro_refcount <= 0:
                await neuro.stop()

    @_grpc_handler
    async def SendGift(self, request, context) -> pb2.GiftResponse:
        log.info(f"SendGift: user={request.user_name} gift={request.gift_name} x{request.count}")
        msg = BridgeMessage(
            msg_type="gift",
            payload=f"{request.gift_name}|{request.count}|{request.user_name}",
            topic=request.stream_id,
            timestamp=time.time(),
        )
        if self.bridge:
            await self.bridge.dispatch(msg)
        thank_you = f"感谢 {request.user_name} 赠送的 {request.count} 个{request.gift_name}!"
        return pb2.GiftResponse(
            success=True, thank_you_text=thank_you,
            reaction_emotion=pb2.EmotionTag(category=pb2.EmotionCategory.HAPPY, intensity=0.8, valence=0.9, arousal=0.6),
            reaction_action=pb2.Live2DTrigger(expression=pb2.ExpressionType.EXPR_HAPPY, motion=pb2.MotionGroup.MOTION_GREETING, intensity=0.7, transition_time=0.3),
        )

    async def shutdown(self):
        log.info("Shutting down gRPC server ...")
        for client_id in list(self.active_streams.keys()):
            self.active_streams[client_id].put_nowait(None)


async def serve_grpc(bridge: BridgeServer, host: str = "0.0.0.0", port: int = 50051, max_workers: int = 10) -> None:
    if not _HAS_PROTO:
        log.error("Cannot start gRPC server: proto stubs not compiled")
        return

    server = grpc.aio.server(options=[
        ("grpc.max_send_message_length", 50 * 1024 * 1024),
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.http2.min_time_between_pings_ms", 10000),
    ])
    servicer = LuminaVirtualHumanServicer(bridge=bridge)
    pb2_grpc.add_VirtualHumanServicer_to_server(servicer, server)
    addr = f"[::]:{port}"
    server.add_insecure_port(addr)
    await server.start()
    log.info(f"gRPC server listening on {addr}")
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        log.info("gRPC server stopped by user")
    finally:
        await servicer.shutdown()
        await server.stop(5)
