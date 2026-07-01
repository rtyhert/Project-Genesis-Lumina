import json
import base64
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

log = logging.getLogger("lumina.api")

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)
    system_prompt: Optional[str] = None


class ChatStreamRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: Optional[str] = None
    speed: Optional[float] = None


class STTRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 encoded audio data")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    emotion: str
    suggested_action: Optional[str] = None


class StatusResponse(BaseModel):
    server: str = "lumina-py"
    version: str = "0.1.0"
    live_active: bool
    live_state: str
    session_count: int
    viewer_count: int
    uptime_seconds: float


def get_server(request: Request):
    server = request.app.state.server
    if not server:
        raise HTTPException(status_code=503, detail="Server not ready")
    return server


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    server = get_server(request)
    try:
        session_id = req.session_id
        if not session_id:
            session_id = await server.chat_handler.create_session()

        response = await server.chat_handler.chat(
            session_id=session_id,
            user_input=req.message,
            system_prompt=req.system_prompt,
        )

        session = await server.chat_handler.get_session(session_id)
        emotion, intensity = session.emotion.get_dominant_emotion() if session else ("neutral", 0.0)
        actions = session.emotion.get_suggested_actions() if session else []

        return ChatResponse(
            session_id=session_id,
            response=response,
            emotion=emotion,
            suggested_action=actions[0] if actions else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatStreamRequest, request: Request):
    server = get_server(request)

    async def event_stream():
        try:
            session_id = req.session_id
            if not session_id:
                session_id = await server.chat_handler.create_session()
                yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

            async for chunk in server.chat_handler.stream_chat(session_id, req.message):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            session = await server.chat_handler.get_session(session_id)
            emotion = session.emotion.get_dominant_emotion()[0] if session else "neutral"
            yield f"data: {json.dumps({'type': 'done', 'emotion': emotion, 'session_id': session_id})}\n\n"
        except Exception as e:
            log.error(f"Stream chat error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tts")
async def tts_endpoint(req: TTSRequest, request: Request):
    server = get_server(request)
    try:
        audio_chunks = []
        async for chunk in server.tts.synthesize(req.text):
            audio_chunks.append(chunk)

        return Response(
            content=b"".join(audio_chunks),
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=tts_output.wav"},
        )
    except Exception as e:
        log.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt")
async def stt_endpoint(req: STTRequest, request: Request):
    server = get_server(request)
    try:
        audio_data = base64.b64decode(req.audio_base64)
        text = await server.stt.transcribe(audio_data)
        return {"text": text or "", "success": text is not None}
    except Exception as e:
        log.error(f"STT error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=StatusResponse)
async def status_endpoint(request: Request):
    server = get_server(request)
    try:
        neuro_status = await server.neuro.get_status()
        session_count = len(server.chat_handler.sessions)

        return StatusResponse(
            live_active=neuro_status["active"],
            live_state=neuro_status["state"],
            session_count=session_count,
            viewer_count=neuro_status["viewer_count"],
            uptime_seconds=server.uptime_seconds,
        )
    except Exception as e:
        log.error(f"Status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/live/start")
async def live_start_endpoint(request: Request):
    server = get_server(request)
    try:
        await server.neuro.start()
        return {"success": True, "message": "Live stream started", "state": server.neuro.state.value}
    except Exception as e:
        log.error(f"Live start error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/live/stop")
async def live_stop_endpoint(request: Request):
    server = get_server(request)
    try:
        await server.neuro.stop()
        return {"success": True, "message": "Live stream stopped"}
    except Exception as e:
        log.error(f"Live stop error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
