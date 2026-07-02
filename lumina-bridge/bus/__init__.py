"""lumina-bridge.bus — In-process event bus for component communication."""
import json
import asyncio
import logging
from typing import Callable, Optional, Awaitable
from dataclasses import dataclass

log = logging.getLogger("lumina.bridge.bus")


@dataclass
class BridgeMessage:
    msg_type: str
    payload: str
    topic: str = ""
    timestamp: float = 0.0


class BridgeServer:
    def __init__(self):
        self.handlers: dict[str, Callable[[BridgeMessage], Awaitable[Optional[BridgeMessage]]]] = {}
        self._running = True

    def register_handler(self, msg_type: str, handler: Callable[[BridgeMessage], Awaitable[Optional[BridgeMessage]]]):
        self.handlers[msg_type] = handler

    async def dispatch(self, msg: BridgeMessage) -> Optional[BridgeMessage]:
        handler = self.handlers.get(msg.msg_type)
        if handler:
            try:
                return await handler(msg)
            except Exception as e:
                log.error(f"Handler error for {msg.msg_type}: {e}")
        return None

    async def start(self):
        log.info("BridgeServer started (in-process event bus)")
        try:
            while self._running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            log.info("BridgeServer cancelled")
        log.info("BridgeServer stopped")

    async def stop(self):
        self._running = False
