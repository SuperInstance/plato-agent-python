#!/usr/bin/env python3
"""Fishing boat demo: 4 rooms with alarm escalation.

Rooms:
  - Engine (temp, rpm, oil_pressure)
  - Bridge (heading, speed, wind)
  - Hold (temperature, humidity, bilge_level)
  - Galley (smoke, temperature, propane)
"""

import asyncio
import sys

from plato_agent.agent import PlatoAgent
from plato_agent.client import PlatoClient
from plato_agent.escalation import EscalationPolicy
from plato_agent.room import RoomState


async def trigger_buzzer(room_name: str, alarm):
    """Simulate triggering a buzzer and light."""
    print(f"🚨 BUZZER + LIGHT for {room_name}: {alarm.name} ({alarm.severity}) — {alarm.message}")


async def send_notification(room_name: str, alarm):
    """Simulate sending a push notification."""
    print(f"📱 NOTIFICATION: {room_name} — {alarm.name}: {alarm.message}")


def create_fishing_boat_agent() -> PlatoAgent:
    """Create a fishing boat agent with rules and escalation policies."""
    agent = PlatoAgent()

    # Escalation: immediate buzzer for critical, notification for warning
    agent.add_escalation(EscalationPolicy(
        timeout=0.0,
        severity_threshold="critical",
        escalate_fn=trigger_buzzer,
    ))
    agent.add_escalation(EscalationPolicy(
        timeout=30.0,
        severity_threshold="warning",
        escalate_fn=send_notification,
    ))

    # Rule: Engine overheating → reduce RPM
    async def reduce_rpm(room: RoomState, agent: PlatoAgent):
        print(f"🌡️ Engine overheating ({room.sensor_values.get('temp')}°) — reducing RPM")
        client = agent.clients.get(room.name)
        if client:
            # In production: await client.actuate("rpm_limit", 1500)
            print("   → ACTUATE rpm_limit=1500")

    agent.add_rule(
        "engine_overheat",
        lambda r: r.name == "engine" and r.sensor_values.get("temp", 0) > 95,
        reduce_rpm,
        cooldown=60.0,
    )

    # Rule: High bilge → activate pump
    async def activate_bilge(room: RoomState, agent: PlatoAgent):
        print(f"🌊 High bilge level ({room.sensor_values.get('bilge_level')}) — activating pump")

    agent.add_rule(
        "high_bilge",
        lambda r: r.name == "hold" and r.sensor_values.get("bilge_level", 0) > 0.8,
        activate_bilge,
        cooldown=30.0,
    )

    return agent


async def run_demo() -> None:
    """Run the fishing boat demo with simulated rooms."""
    agent = create_fishing_boat_agent()

    # In production, connect to real rooms:
    # for name, port in [("engine", 7001), ("bridge", 7002), ("hold", 7003), ("galley", 7004)]:
    #     client = PlatoClient()
    #     await client.connect("localhost", port)
    #     agent.add_room(name, client)

    # Demo: simulate rooms directly
    from plato_agent.protocol import TickData

    for name in ["engine", "bridge", "hold", "galley"]:
        room = agent.add_room(name, None)  # type: ignore

    # Simulate some ticks
    print("=== Fishing Boat Demo ===\n")

    # Normal operation
    print("--- Normal Operation ---")
    await agent._process_tick("engine", TickData(1.0, {"temp": 85, "rpm": 2200, "oil_pressure": 40}))
    await agent._process_tick("bridge", TickData(1.0, {"heading": 270, "speed": 8.5, "wind": 15}))
    await agent._process_tick("hold", TickData(1.0, {"temperature": 38, "humidity": 65, "bilge_level": 0.3}))
    await agent._process_tick("galley", TickData(1.0, {"smoke": 0, "temperature": 72, "propane": "off"}))

    # Engine overheating
    print("\n--- Engine Overheating ---")
    await agent._process_tick("engine", TickData(2.0, {"temp": 98, "rpm": 2400, "oil_pressure": 35}))
    await agent._process_alarm("engine", __import__("plato_agent.protocol", fromlist=["AlarmNotification"]).AlarmNotification(
        "engine_overheat", "critical", "Engine temperature 98°C exceeds safe limit"
    ))

    # High bilge
    print("\n--- Rising Bilge Water ---")
    await agent._process_tick("hold", TickData(2.0, {"temperature": 38, "humidity": 70, "bilge_level": 0.85}))

    # Cross-room correlations
    print("\n--- Cross-Room Correlations ---")
    corrs = agent.get_cross_room_correlations()
    for corr in corrs:
        print(f"  {corr}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(run_demo())
