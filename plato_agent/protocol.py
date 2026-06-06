"""Wire protocol parser and formatter for Plato room communication.

Protocol spec (text-based, newline-delimited):
  Responses from room:
    TICK <timestamp> <json-sensor-payload>
    HISTORY <cursor> <count> <json-array-of-ticks>
    ALARM <alarm-name> <severity> <message>
    ALARM_CLEARED <alarm-name>
    ACK <command>
    ERROR <message>

  Commands from agent:
    TICK
    HISTORY <n>
    HISTORY_CURSOR <cursor>
    ACTUATE <name>=<value>
    SUBSCRIBE
    UNSUBSCRIBE
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TickData:
    """A single tick from a room."""
    timestamp: float
    sensors: dict[str, Any]


@dataclass
class HistoryData:
    """History response from a room."""
    cursor: int
    count: int
    ticks: list[TickData]


@dataclass
class AlarmNotification:
    """An alarm notification from a room."""
    name: str
    severity: str
    message: str


@dataclass
class AlarmCleared:
    """An alarm cleared notification."""
    name: str


@dataclass
class AckResponse:
    """Acknowledgement of a command."""
    command: str


@dataclass
class ErrorResponse:
    """Error response from a room."""
    message: str


def parse_response(line: str) -> TickData | HistoryData | AlarmNotification | AlarmCleared | AckResponse | ErrorResponse:
    """Parse a single protocol line into a typed object.

    Args:
        line: Raw protocol line (without trailing newline).

    Returns:
        Typed data object.

    Raises:
        ProtocolError: If the line cannot be parsed.
    """
    line = line.strip()
    if not line:
        raise ProtocolError("Empty line")

    if line.startswith("TICK "):
        parts = line.split(" ", 2)
        if len(parts) < 3:
            raise ProtocolError(f"Malformed TICK: {line}")
        try:
            timestamp = float(parts[1])
            sensors = json.loads(parts[2])
        except (ValueError, json.JSONDecodeError) as e:
            raise ProtocolError(f"Malformed TICK payload: {line}") from e
        return TickData(timestamp=timestamp, sensors=sensors)

    if line.startswith("HISTORY "):
        parts = line.split(" ", 3)
        if len(parts) < 4:
            raise ProtocolError(f"Malformed HISTORY: {line}")
        try:
            cursor = int(parts[1])
            count = int(parts[2])
            raw_ticks = json.loads(parts[3])
        except (ValueError, json.JSONDecodeError) as e:
            raise ProtocolError(f"Malformed HISTORY payload: {line}") from e
        ticks = [
            TickData(timestamp=t["ts"], sensors=t["sensors"])
            for t in raw_ticks
        ]
        return HistoryData(cursor=cursor, count=count, ticks=ticks)

    if line.startswith("ALARM_CLEARED "):
        name = line.split(" ", 1)[1].strip()
        return AlarmCleared(name=name)

    if line.startswith("ALARM "):
        parts = line.split(" ", 3)
        if len(parts) < 4:
            raise ProtocolError(f"Malformed ALARM: {line}")
        return AlarmNotification(
            name=parts[1],
            severity=parts[2],
            message=parts[3],
        )

    if line.startswith("ACK "):
        return AckResponse(command=line[4:].strip())

    if line.startswith("ERROR "):
        return ErrorResponse(message=line[6:].strip())

    raise ProtocolError(f"Unknown protocol line: {line}")


def format_command(cmd: str, **kwargs: Any) -> str:
    """Format an agent command into a protocol line.

    Args:
        cmd: Command name (TICK, HISTORY, ACTUATE, SUBSCRIBE, UNSUBSCRIBE).
        **kwargs: Command parameters.

    Returns:
        Formatted protocol line (without newline).

    Raises:
        ProtocolError: If required parameters are missing.
    """
    cmd = cmd.upper().strip()

    if cmd == "TICK":
        return "TICK"

    if cmd == "HISTORY":
        n = kwargs.get("n", 10)
        return f"HISTORY {n}"

    if cmd == "HISTORY_CURSOR":
        cursor = kwargs.get("cursor")
        if cursor is None:
            raise ProtocolError("HISTORY_CURSOR requires 'cursor' parameter")
        return f"HISTORY_CURSOR {cursor}"

    if cmd == "ACTUATE":
        name = kwargs.get("name")
        value = kwargs.get("value")
        if name is None or value is None:
            raise ProtocolError("ACTUATE requires 'name' and 'value' parameters")
        return f"ACTUATE {name}={value}"

    if cmd == "SUBSCRIBE":
        return "SUBSCRIBE"

    if cmd == "UNSUBSCRIBE":
        return "UNSUBSCRIBE"

    raise ProtocolError(f"Unknown command: {cmd}")


class ProtocolError(Exception):
    """Error in protocol parsing or formatting."""
