import asyncio
import signal
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .server import UpageServer
from .api_routes import router as api_router

log = logging.getLogger("upage")


def create_app(server: UpageServer) -> FastAPI:
    app = FastAPI(
        title="upage-py",
        version="0.1.0",
        description="uPage AI Backend - Virtual Human Live Streaming Platform",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.server = server

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "upage-py"}

    return app


async def main():
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    server = UpageServer(str(config_path))
    server.log.info("UpageServer initialized")

    app = create_app(server)

    grpc_task = asyncio.create_task(server.start_grpc())

    rest_config = uvicorn.Config(
        app=app,
        host=server.cfg["server"].get("host", "0.0.0.0"),
        port=server.cfg["server"].get("rest_port", 8000),
        log_level="info",
        reload=server.cfg.get("hot_reload", False),
    )
    rest_server = uvicorn.Server(rest_config)

    shutdown_event = asyncio.Event()

    def _signal_handler():
        server.log.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    server.log.info(
        f"Starting REST API on {rest_config.host}:{rest_config.port}, "
        f"gRPC on port {server.cfg['server']['port']}"
    )

    rest_task = asyncio.create_task(rest_server.serve())

    done, pending = await asyncio.wait(
        [
            grpc_task,
            rest_task,
            asyncio.create_task(shutdown_event.wait()),
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )

    server.log.info("Shutting down gracefully...")
    for task in pending:
        task.cancel()

    rest_server.should_exit = True
    await server.neuro.stop()

    server.log.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
