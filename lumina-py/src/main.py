"""Lumina application entry point — FastAPI + gRPC launcher with graceful shutdown."""
import asyncio
import os
import signal
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server import LuminaServer
from api_routes import router as api_router
from metrics import get_metrics_collector

log = logging.getLogger("lumina")


def _add_auth_middleware(app: FastAPI, api_key: str, exclude_paths: list):
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        for prefix in exclude_paths:
            if request.url.path.startswith(prefix):
                return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != api_key:
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})
        return await call_next(request)


def _add_rate_limit_middleware(app: FastAPI, requests_per_minute: int):
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(key_func=get_remote_address, default_limits=[f"{requests_per_minute}/minute"])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        log.info("Rate limiting enabled: %s req/min", requests_per_minute)
    except ImportError:
        log.warning("slowapi not installed; rate limiting disabled (pip install slowapi)")


def create_app(server: LuminaServer) -> FastAPI:
    app = FastAPI(
        title="lumina-py",
        version="0.1.0",
        description="Lumina AI Backend — Virtual Human Live Streaming Platform",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.server = server
    app.include_router(api_router, prefix="/api/v1")

    if server.cfg.auth.enabled and server.cfg.auth.api_key:
        _add_auth_middleware(app, server.cfg.auth.api_key, server.cfg.auth.exclude_paths)
        log.info("API key authentication enabled")

    if server.cfg.rate_limit.enabled:
        _add_rate_limit_middleware(app, server.cfg.rate_limit.requests_per_minute)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        mc = get_metrics_collector()
        ep = request.url.path
        mc.inc_request(ep)
        import time as tmod
        start = tmod.time()
        try:
            resp = await call_next(request)
            return resp
        except Exception:
            mc.inc_error(ep)
            raise
        finally:
            mc.record_latency(ep, tmod.time() - start)

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": "lumina-py",
            "mock_mode": server.mock_mode,
            "uptime": server.uptime_seconds,
        }

    @app.get("/metrics")
    async def metrics():
        mc = get_metrics_collector()
        return mc.snapshot()

    return app


def _can_use_signal_handlers() -> bool:
    return os.name != "nt"


async def run():
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"

    mock_env = os.environ.get("LUMINA_MOCK", "")
    if mock_env:
        log.info(f"LUMINA_MOCK={mock_env} from environment")

    server = LuminaServer(str(config_path))
    server.chat_handler.start_cleanup_task()
    server.log.info("LuminaServer initialized")

    app = create_app(server)

    grpc_task = asyncio.create_task(server.start_grpc())

    rest_config = uvicorn.Config(
        app=app,
        host=server.cfg.server.host,
        port=server.cfg.server.rest_port,
        log_level="info",
        reload=server.cfg.hot_reload,
    )
    rest_server = uvicorn.Server(rest_config)

    shutdown_event = asyncio.Event()

    def _signal_handler():
        server.log.info("Shutdown signal received")
        shutdown_event.set()

    if _can_use_signal_handlers():
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        server.log.info("Signal handlers not available on Windows; use Ctrl+C to stop")

    server.log.info(
        f"Starting REST API on {rest_config.host}:{rest_config.port}, "
        f"gRPC on port {server.cfg.server.port}, "
        f"mock_mode={server.mock_mode}"
    )

    rest_task = asyncio.create_task(rest_server.serve())
    waiters = [grpc_task, rest_task, asyncio.create_task(shutdown_event.wait())]

    done, pending = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        exc = task.exception()
        if exc:
            server.log.error("Task failed: %s", exc)

    server.log.info("Shutting down gracefully...")
    for task in pending:
        task.cancel()
    rest_server.should_exit = True
    await server.neuro.stop()
    from thread_pool import shutdown_io_executor
    shutdown_io_executor()
    server.log.info("Shutdown complete")


def main():
    """Entry point for `python -m lumina_py.src.main` or `python start.py`."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Received keyboard interrupt")


if __name__ == "__main__":
    main()
