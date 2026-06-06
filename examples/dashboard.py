#!/usr/bin/env python3
"""Text-based dashboard using rich for Plato room monitoring."""

import asyncio
import sys

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from plato_agent.agent import PlatoAgent
from plato_agent.client import PlatoClient
from plato_agent.protocol import TickData


def build_dashboard(agent: PlatoAgent):
    """Build a rich Table from agent state."""
    table = Table(title="Plato Room Dashboard")
    table.add_column("Room", style="cyan")
    table.add_column("Sensors", style="white")
    table.add_column("Alarms", style="red")
    table.add_column("History", style="dim")

    for name, room in agent.rooms.items():
        sensors = "  ".join(f"{k}={v}" for k, v in room.sensor_values.items()) or "—"
        alarms = ", ".join(a.name for a in room.active_alarms) or "✓ OK"
        history = f"{len(room.history)} ticks"

        style = "red" if room.active_alarms else "green"
        table.add_row(name, sensors, alarms, history, style=style)

    return table


async def dashboard(host: str, port: int) -> None:
    if not HAS_RICH:
        print("Install rich: pip install rich")
        return

    console = Console()
    agent = PlatoAgent()
    client = PlatoClient()
    await client.connect(host, port)
    room = agent.add_room("room-1", client)

    with Live(console=console, refresh_per_second=4) as live:
        # Fetch current state
        tick = await client.tick()
        room.update_from_tick(tick)
        live.update(build_dashboard(agent))

        # Stream updates
        await client.subscribe()
        async for event in client.stream():
            if isinstance(event, TickData):
                room.update_from_tick(event)
            live.update(build_dashboard(agent))

    await client.disconnect()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7001
    asyncio.run(dashboard(host, port))
