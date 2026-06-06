"""Plato Agent Framework — connect to Plato rooms, observe ticks, send commands."""

from .client import PlatoClient
from .room import RoomState, Tick, AlarmState
from .agent import PlatoAgent
from .protocol import parse_response, format_command
from .escalation import EscalationPolicy
from .config import RoomConfig
from .summary import summarize_ticks

__all__ = [
    "PlatoClient",
    "RoomState",
    "Tick",
    "AlarmState",
    "PlatoAgent",
    "parse_response",
    "format_command",
    "EscalationPolicy",
    "RoomConfig",
    "summarize_ticks",
]
__version__ = "0.1.0"
