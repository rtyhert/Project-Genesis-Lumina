"""Deprecated — import from lumina_bridge.bus instead.

Moved to: lumina_bridge.bus.BridgeServer, lumina_bridge.bus.BridgeMessage
"""
import warnings
warnings.warn(
    "lumina-bridge/src/bridge_server.py is deprecated. "
    "Use `from lumina_bridge.bus import BridgeServer, BridgeMessage` instead.",
    DeprecationWarning, stacklevel=2,
)
from lumina_bridge.bus import BridgeServer, BridgeMessage

__all__ = ["BridgeServer", "BridgeMessage"]
