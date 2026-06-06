"""Room state tracking for Plato Engine Blocks."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from .protocol import TickData


@dataclass
class Tick:
    """A processed tick with room context."""
    timestamp: float
    sensors: dict[str, Any]
    room_name: str = ""


@dataclass
class AlarmState:
    """An active or historical alarm."""
    name: str
    severity: str
    message: str
    active: bool = True
    raised_at: float = 0.0
    cleared_at: float | None = None


class RoomState:
    """Tracks a room's sensors, rolling history, and alarms.

    Attributes:
        name: Room identifier.
        sensor_values: Latest sensor readings keyed by sensor name.
        history: Rolling list of recent ticks.
        alarms: Active alarm states keyed by alarm name.
        max_history: Maximum number of ticks to retain.
    """

    def __init__(self, name: str, max_history: int = 1000) -> None:
        self.name = name
        self.sensor_values: dict[str, Any] = {}
        self.history: list[Tick] = []
        self.alarms: dict[str, AlarmState] = {}
        self.max_history = max_history

    def update_from_tick(self, tick: TickData) -> Tick:
        """Process an incoming tick and update room state.

        Args:
            tick: Raw tick data from protocol parser.

        Returns:
            Processed Tick with room context.
        """
        processed = Tick(
            timestamp=tick.timestamp,
            sensors=dict(tick.sensors),
            room_name=self.name,
        )
        self.sensor_values.update(tick.sensors)
        self.history.append(processed)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        return processed

    def raise_alarm(self, name: str, severity: str, message: str, timestamp: float = 0.0) -> AlarmState:
        """Raise a new alarm or update an existing one.

        Returns:
            The alarm state.
        """
        alarm = AlarmState(
            name=name,
            severity=severity,
            message=message,
            active=True,
            raised_at=timestamp,
        )
        self.alarms[name] = alarm
        return alarm

    def clear_alarm(self, name: str, timestamp: float = 0.0) -> AlarmState | None:
        """Clear an alarm.

        Returns:
            The cleared alarm state, or None if not found.
        """
        alarm = self.alarms.get(name)
        if alarm is None:
            return None
        alarm.active = False
        alarm.cleared_at = timestamp
        return alarm

    @property
    def active_alarms(self) -> list[AlarmState]:
        """Return all currently active alarms."""
        return [a for a in self.alarms.values() if a.active]

    def get_trend(self, sensor: str, window: int | None = None) -> dict[str, Any]:
        """Compute trend statistics for a sensor over the last N ticks.

        Args:
            sensor: Sensor name to analyze.
            window: Number of recent ticks to consider (default: all history).

        Returns:
            Dict with 'latest', 'mean', 'min', 'max', 'stddev', 'slope', 'direction'.
            Returns empty dict if no numeric data available.
        """
        if window is not None:
            ticks = self.history[-window:]
        else:
            ticks = self.history

        values = []
        for t in ticks:
            v = t.sensors.get(sensor)
            if v is not None and isinstance(v, (int, float)):
                values.append(v)

        if not values:
            return {}

        mean_val = statistics.mean(values)
        result: dict[str, Any] = {
            "latest": values[-1],
            "mean": mean_val,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

        if len(values) >= 2:
            result["stddev"] = statistics.stdev(values)
            # Simple linear regression slope
            n = len(values)
            x_mean = (n - 1) / 2.0
            numerator = sum((i - x_mean) * (v - mean_val) for i, v in enumerate(values))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            if denominator != 0:
                slope = numerator / denominator
                result["slope"] = slope
                result["direction"] = "rising" if slope > 0 else "falling" if slope < 0 else "flat"
            else:
                result["slope"] = 0.0
                result["direction"] = "flat"
        else:
            result["stddev"] = 0.0
            result["slope"] = 0.0
            result["direction"] = "flat"

        return result

    def __repr__(self) -> str:
        return (
            f"RoomState(name={self.name!r}, "
            f"sensors={len(self.sensor_values)}, "
            f"history={len(self.history)}, "
            f"alarms={len(self.active_alarms)} active)"
        )
