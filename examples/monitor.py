#!/usr/bin/env python3
"""Monitor: Connect to a Plato room, stream ticks, print alerts."""

import asyncio
import sys

from plato_agent.client import PlatoClient
from plato_agent.protocol import AlarmNotification, TickData


async def monitor(host: str, port: int) -> None:
    client = PlatoClient()
    await client.connect(host, port)
    print(f"Connected to {host}:{port}")

    await client.subscribe()
    print("Subscribed. Streaming ticks... (Ctrl+C to stop)")

    try:
        async for event in client.stream():
            if isinstance(event, TickData):
                print(f"[{event.timestamp:.1f}] {event.sensors}")
            elif isinstance(event, AlarmNotification):
                print(f"⚠️  ALARM: {event.name} ({event.severity}): {event.message}")
    except KeyboardInterrupt:
        pass
    finally:
        await client.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7001
    asyncio.run(monitor(host, port))
