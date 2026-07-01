"""
upage-bridge: Python-side IPC bridge for gRPC communication.
"""
import json
import struct
import asyncio
from typing import Callable, Optional
from dataclasses import dataclass, asdict

@dataclass
class BridgeMessage:
    msg_type: str
    payload: str
    topic: str = ""
    timestamp: float = 0.0

class BridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 50051):
        self.host = host
        self.port = port
        self.handlers: dict[str, Callable] = {}

    def register_handler(self, msg_type: str, handler: Callable):
        self.handlers[msg_type] = handler

    async def dispatch(self, msg: BridgeMessage) -> Optional[BridgeMessage]:
        handler = self.handlers.get(msg.msg_type)
        if handler:
            result = await handler(msg)
            return result
        return None

    async def start(self):
        print(f"[BridgeServer] Listening on {self.host}:{self.port}")
        while True:
            await asyncio.sleep(0.01)
