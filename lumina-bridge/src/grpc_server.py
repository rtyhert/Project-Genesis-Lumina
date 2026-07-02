"""Deprecated — import from lumina_bridge.grpc instead.

Moved to: lumina_bridge.grpc.LuminaVirtualHumanServicer, lumina_bridge.grpc.serve_grpc
"""
import warnings
warnings.warn(
    "lumina-bridge/src/grpc_server.py is deprecated. "
    "Use `from lumina_bridge.grpc import LuminaVirtualHumanServicer, serve_grpc` instead.",
    DeprecationWarning, stacklevel=2,
)
from lumina_bridge.grpc import LuminaVirtualHumanServicer, serve_grpc

__all__ = ["LuminaVirtualHumanServicer", "serve_grpc"]
