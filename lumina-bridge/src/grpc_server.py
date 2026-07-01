import asyncio
import logging
import time
from typing import AsyncIterator, Optional

import grpc

from lumina_bridge.bridge_server import BridgeServer, BridgeMessage

try:
    from lumina_proto.build import lumina_pb2 as pb2
    from lumina_proto.build import lumina_pb2_grpc as pb2_grpc
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lumina-proto" / "build"))
    import lumina_pb2 as pb2
    import lumina_pb2_grpc as pb2_grpc

log = logging.getLogger("lumina.grpc")

class VirtualHumanServicer(pb2_grpc.VirtualHumanServicer):
    def __init__(self, bridge: BridgeServer):
        self.bridge = bridge
        self.active_streams: dict[str, asyncio.Queue] = {}
        self.emotion_history: dict[str, list] = {}

    # ============== Chat ==============

    async def ProcessChat(
        self, request: pb2.ChatRequest, context: grpc.aio.ServicerContext
    ) -> pb2.ChatResponse:
        log.info(f"ProcessChat: user={request.user_id} msg={request.message[:60]}")
        try:
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
        except Exception as e:
            log.error(f"ProcessChat failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
        return pb2.ChatResponse(reply_text="[System] 抱歉，我暂时无法回复")

    # ============== Audio ==============

    async def StreamAudio(
        self, request: pb2.AudioRequest, context: grpc.aio.ServicerContext
    ) -> AsyncIterator[pb2.AudioChunk]:
        log.info(f"StreamAudio: text={request.text[:40]} voice={request.voice_id}")
        try:
            from lumina_py.src.tts_engine import TTSEngine
            tts = TTSEngine({
                "engine": "edge-tts",
                "voice": request.voice_id or "zh-CN-XiaoxiaoNeural",
                "speed": request.speed or 1.0,
            })
            seq = 0
            async for data in tts.synthesize(request.text):
                chunk = pb2.AudioChunk(
                    data=data,
                    timestamp=int(time.time() * 1000),
                    is_final=False,
                    sequence=seq,
                )
                yield chunk
                seq += 1
            yield pb2.AudioChunk(data=b"", timestamp=int(time.time() * 1000), is_final=True, sequence=seq)
        except Exception as e:
            log.error(f"StreamAudio failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

    async def ProcessAudioStream(
        self, request_iterator: AsyncIterator[pb2.AudioUpload], context: grpc.aio.ServicerContext
    ) -> pb2.STTResult:
        log.info("ProcessAudioStream: receiving audio stream")
        audio_buffer = bytearray()
        session_id = ""
        try:
            async for chunk in request_iterator:
                audio_buffer.extend(chunk.data)
                if chunk.session_id:
                    session_id = chunk.session_id
                if chunk.is_final:
                    break
            from lumina_py.src.stt_engine import STTEngine
            stt = STTEngine({"engine": "whisper", "model": "base"})
            text = await stt.transcribe(bytes(audio_buffer))
            return pb2.STTResult(
                text=text or "",
                confidence=0.85,
                is_final=True,
                language="zh",
            )
        except Exception as e:
            log.error(f"ProcessAudioStream failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.STTResult(text="", confidence=0.0, is_final=True, language="zh")

    # ============== Lip Sync ==============

    async def SyncLip(
        self, request: pb2.LipSyncRequest, context: grpc.aio.ServicerContext
    ) -> pb2.LipSyncData:
        log.info(f"SyncLip: text={request.text[:40]}")
        try:
            msg = BridgeMessage(
                msg_type="lip_sync",
                payload=request.text,
                topic=request.language,
                timestamp=time.time(),
            )
            result = await self.bridge.dispatch(msg)
            frames = []
            duration = 0.0
            if result and result.payload:
                import json
                try:
                    data = json.loads(result.payload)
                    for f in data.get("frames", []):
                        frames.append(pb2.LipFrame(
                            time=f.get("t", 0.0),
                            mouth_open=f.get("mo", 0.0),
                            jaw_y=f.get("jy", 0.0),
                            tongue_x=f.get("tx", 0.0),
                            tongue_y=f.get("ty", 0.0),
                            lip_width=f.get("lw", 0.0),
                        ))
                    duration = data.get("duration", 0.0)
                except json.JSONDecodeError:
                    pass
            return pb2.LipSyncData(frames=frames, total_duration=duration)
        except Exception as e:
            log.error(f"SyncLip failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.LipSyncData()

    # ============== Action ==============

    async def TriggerAction(
        self, request: pb2.ActionRequest, context: grpc.aio.ServicerContext
    ) -> pb2.ActionResponse:
        log.info(f"TriggerAction: type={request.action_type} emotion={request.emotion}")
        try:
            msg = BridgeMessage(
                msg_type="action_trigger",
                payload=f"{request.action_type}|{request.emotion}|{request.intensity}",
                timestamp=time.time(),
            )
            result = await self.bridge.dispatch(msg)
            if result and result.payload:
                return pb2.ActionResponse(
                    success=True,
                    animation_id=result.payload,
                    duration=request.intensity * 2.0,
                )
            return pb2.ActionResponse(success=True, animation_id=request.action_type, duration=1.0)
        except Exception as e:
            log.error(f"TriggerAction failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.ActionResponse(success=False, error_message=str(e))

    # ============== Emotion ==============

    async def SendEmotion(
        self, request: pb2.EmotionRequest, context: grpc.aio.ServicerContext
    ) -> pb2.EmotionResponse:
        log.info(f"SendEmotion: session={request.session_id} cat={request.emotion.category}")
        try:
            tag = request.emotion
            if request.session_id not in self.emotion_history:
                self.emotion_history[request.session_id] = []
            self.emotion_history[request.session_id].append(tag)

            from lumina_py.src.neuro_engine import NeuroEngine
            neuro = NeuroEngine({"stream_mode": "simulate"}, None)

            msg = BridgeMessage(
                msg_type="emotion",
                payload=f"{tag.category}|{tag.intensity}|{tag.valence}|{tag.arousal}",
                topic=request.session_id,
                timestamp=time.time(),
            )
            await self.bridge.dispatch(msg)

            transition = "idle"
            if tag.category == pb2.EmotionCategory.HAPPY:
                transition = "happy"
            elif tag.category == pb2.EmotionCategory.SAD:
                transition = "sad"
            elif tag.category == pb2.EmotionCategory.ANGRY:
                transition = "angry"

            return pb2.EmotionResponse(
                success=True,
                resulting_emotion=tag,
                transition_animation=transition,
            )
        except Exception as e:
            log.error(f"SendEmotion failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.EmotionResponse(success=False)

    # ============== Live2D ==============

    async def Live2DControl(
        self, request: pb2.Live2DCommand, context: grpc.aio.ServicerContext
    ) -> pb2.Live2DResponse:
        log.info(f"Live2DControl: session={request.session_id}")
        try:
            cmd_type = request.WhichOneof("command")
            payload = f"{cmd_type}|{request.transition_time}|{request.queue}|{request.priority}"

            if cmd_type == "expression":
                ctrl = request.expression
                payload += f"|{ctrl.type}|{ctrl.intensity}|{ctrl.duration}"
            elif cmd_type == "motion":
                ctrl = request.motion
                payload += f"|{ctrl.group}|{ctrl.animation_id}|{ctrl.speed}|{ctrl.loop}"
            elif cmd_type == "param":
                ctrl = request.param
                payload += f"|{ctrl.param_name}|{ctrl.value}"
            elif cmd_type == "lip_sync":
                ctrl = request.lip_sync
                payload += f"|{ctrl.enabled}|{ctrl.gain}"
            elif cmd_type == "physics":
                ctrl = request.physics
                payload += f"|{ctrl.enabled}|{ctrl.reset}"

            msg = BridgeMessage(
                msg_type="live2d",
                payload=payload,
                topic=request.session_id,
                timestamp=time.time(),
            )
            result = await self.bridge.dispatch(msg)
            anim_id = result.payload if result and result.payload else "anim_default"
            return pb2.Live2DResponse(
                success=True,
                animation_id=anim_id,
                transition_duration=request.transition_time,
            )
        except Exception as e:
            log.error(f"Live2DControl failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.Live2DResponse(success=False, error=str(e))

    # ============== Stream Status ==============

    async def StreamStatus(
        self, request: pb2.StatusRequest, context: grpc.aio.ServicerContext
    ) -> AsyncIterator[pb2.StatusEvent]:
        log.info(f"StreamStatus: client={request.client_id} events={request.subscribed_events}")
        queue: asyncio.Queue = asyncio.Queue()
        self.active_streams[request.client_id] = queue
        try:
            while True:
                if context.cancelled():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    event = pb2.StatusEvent(
                        event_type=payload.get("type", "heartbeat"),
                        payload=payload.get("data", ""),
                        timestamp=int(time.time() * 1000),
                    )
                    yield event
                except asyncio.TimeoutError:
                    yield pb2.StatusEvent(
                        event_type="heartbeat",
                        payload="",
                        timestamp=int(time.time() * 1000),
                    )
        finally:
            self.active_streams.pop(request.client_id, None)
            log.info(f"StreamStatus: client {request.client_id} disconnected")

    async def StreamLiveStatus(
        self, request: pb2.LiveStatusRequest, context: grpc.aio.ServicerContext
    ) -> AsyncIterator[pb2.LiveStatusEvent]:
        log.info(f"StreamLiveStatus: stream={request.stream_id} platform={request.platform}")
        from lumina_py.src.neuro_engine import NeuroEngine
        neuro = NeuroEngine({"stream_mode": "simulate", "audience_size": 10}, None)

        async def on_event(text: str):
            event = pb2.LiveStatusEvent(
                stream_id=request.stream_id,
                event_type=pb2.LiveEventType.AUDIENCE_MESSAGE,
                timestamp=int(time.time() * 1000),
                event_id=int(time.time() * 1000000),
            )
            event.audience_msg.message = text
            return event

        try:
            async def event_generator():
                while not context.cancelled():
                    if neuro.active:
                        simulated = neuro._simulate_chat()
                        if simulated:
                            event = pb2.LiveStatusEvent(
                                stream_id=request.stream_id,
                                event_type=pb2.LiveEventType.AUDIENCE_MESSAGE,
                                timestamp=int(time.time() * 1000),
                                event_id=int(time.time() * 1000000),
                            )
                            event.audience_msg.message = simulated
                            yield event
                    await asyncio.sleep(3.0)

            async for ev in event_generator():
                yield ev
        finally:
            neuro.stop()

    # ============== Gift ==============

    async def SendGift(
        self, request: pb2.GiftNotify, context: grpc.aio.ServicerContext
    ) -> pb2.GiftResponse:
        log.info(f"SendGift: user={request.user_name} gift={request.gift_name} x{request.count}")
        try:
            msg = BridgeMessage(
                msg_type="gift",
                payload=f"{request.gift_name}|{request.count}|{request.user_name}",
                topic=request.stream_id,
                timestamp=time.time(),
            )
            result = await self.bridge.dispatch(msg)
            thank_you = f"感谢 {request.user_name} 赠送的 {request.count} 个{request.gift_name}!"
            return pb2.GiftResponse(
                success=True,
                thank_you_text=thank_you,
                reaction_emotion=pb2.EmotionTag(
                    category=pb2.EmotionCategory.HAPPY,
                    intensity=0.8,
                    valence=0.9,
                    arousal=0.6,
                ),
                reaction_action=pb2.Live2DTrigger(
                    expression=pb2.ExpressionType.EXPR_HAPPY,
                    motion=pb2.MotionGroup.MOTION_GREETING,
                    intensity=0.7,
                    transition_time=0.3,
                ),
            )
        except Exception as e:
            log.error(f"SendGift failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.GiftResponse(success=False)

    # ============== Lifecycle ==============

    async def shutdown(self):
        log.info("Shutting down gRPC server ...")
        for client_id in list(self.active_streams.keys()):
            self.active_streams[client_id].put_nowait(None)


async def serve_grpc(
    bridge: BridgeServer,
    host: str = "0.0.0.0",
    port: int = 50051,
    max_workers: int = 10,
) -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
            ("grpc.http2.min_time_between_pings_ms", 10000),
        ],
    )
    servicer = VirtualHumanServicer(bridge)
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
