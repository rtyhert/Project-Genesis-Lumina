"""lumina-bridge — IPC communication bridge.

Sub-packages:
  lumina_bridge.bus   — In-process event bus (BridgeServer, BridgeMessage)
  lumina_bridge.grpc  — gRPC servicer (LuminaVirtualHumanServicer, serve_grpc)
  lumina_bridge.ipc   — C++ IPC channel (header + implementation)
"""
from lumina_bridge.bus import BridgeServer, BridgeMessage
from lumina_bridge.grpc import LuminaVirtualHumanServicer, serve_grpc

__all__ = ["BridgeServer", "BridgeMessage", "LuminaVirtualHumanServicer", "serve_grpc"]
