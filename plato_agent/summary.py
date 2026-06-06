"""Summarize tick history into natural language."""

from __future__ import annotations

from typing import Any

from .room import Tick


def summarize_ticks(ticks: list[Tick], room_name: str = "") -> str:
    """Summarize a list of ticks into a human-readable paragraph.

    Args:
        ticks: List of ticks to summarize.
        room_name: Optional room name for context.

    Returns:
        Natural language summary string.
    """
    if not ticks:
        prefix = f"Room {room_name}: " if room_name else "Room: "
        return f"{prefix}No tick data available."

    first = ticks[0]
    last = ticks[-1]
    duration = last.timestamp - first.timestamp

    parts: list[str] = []
    if room_name:
        parts.append(f"Room **{room_name}**")

    # Collect all sensor names
    all_sensors: set[str] = set()
    for t in ticks:
        all_sensors.update(t.sensors.keys())

    # Summarize each sensor
    sensor_summaries = []
    for sensor in sorted(all_sensors):
        values = [
            t.sensors[sensor] for t in ticks
            if sensor in t.sensors and isinstance(t.sensors[sensor], (int, float))
        ]
        if not values:
            continue

        latest = values[-1]
        min_val = min(values)
        max_val = max(values)

        if len(values) >= 2:
            direction = "↑" if values[-1] > values[0] else "↓" if values[-1] < values[0] else "→"
            sensor_summaries.append(
                f"{sensor}: {latest} (range {min_val}–{max_val}, {direction})"
            )
        else:
            sensor_summaries.append(f"{sensor}: {latest}")

    parts.append(f"{len(ticks)} ticks over {duration:.1f}s")
    if sensor_summaries:
        parts.append("Sensors: " + ", ".join(sensor_summaries))

    return ". ".join(parts) + "."
