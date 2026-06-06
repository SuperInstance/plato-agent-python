# Plug & Play — Plato Agent Python

Copy-paste templates for the three most common patterns.

## Pattern 1: Connect and Observe

```python
import asyncio
from plato_agent import PlatoClient

async def main():
    client = PlatoClient()
    await client.connect("localhost", 7001)

    # Single tick
    tick = await client.tick()
    print(f"Sensors: {tick.sensors}")

    # Stream live updates
    await client.subscribe()
    async for event in client.stream():
        print(f"Update: {event.sensors}")

    await client.disconnect()

asyncio.run(main())
```

## Pattern 2: Rule-Based Agent

```python
import asyncio
from plato_agent import PlatoAgent, PlatoClient, EscalationPolicy

async def alert(room_name, alarm):
    print(f"🚨 {room_name}: {alarm.message}")

async def main():
    agent = PlatoAgent()
    client = PlatoClient()
    await client.connect("localhost", 7001)
    agent.add_room("engine", client)

    # Rule: overheat → activate fan
    agent.add_rule(
        "overheat",
        lambda r: r.sensor_values.get("temp", 0) > 80,
        lambda r, a: print(f"🔥 Hot! {r.sensor_values['temp']}°C"),
        cooldown=30,
    )

    # Escalation: critical alarms → SMS
    agent.add_escalation(EscalationPolicy(
        timeout=60.0,
        severity_threshold="critical",
        escalate_fn=alert,
    ))

    await agent.run()

asyncio.run(main())
```

## Pattern 3: Multi-Room with Config Files

```python
import asyncio
from plato_agent import PlatoAgent, PlatoClient, RoomConfig

async def main():
    agent = PlatoAgent()

    # Load room configs from a directory
    for cfg in RoomConfig.load_directory("rooms/"):
        client = PlatoClient()
        await client.connect(cfg.host, cfg.port)
        agent.add_room(cfg.name, client)
        print(f"Connected to {cfg.name} ({cfg.host}:{cfg.port})")

    # Add rules
    agent.add_rule(
        "any_alarm",
        lambda r: bool(r.active_alarms),
        lambda r, a: print(f"[{r.name}] Alarms: {[al.name for al in r.active_alarms]}"),
        cooldown=10,
    )

    await agent.run()

asyncio.run(main())
```

## Quick Reference

| What | Code |
|------|------|
| Connect | `await client.connect("host", port)` |
| Tick | `tick = await client.tick()` |
| History | `h = await client.history(n=10)` |
| Actuate | `await client.actuate("fan", 75)` |
| Subscribe | `await client.subscribe()` |
| Stream | `async for event in client.stream():` |
| Add rule | `agent.add_rule(name, condition_fn, action_fn, cooldown=30)` |
| Add escalation | `agent.add_escalation(EscalationPolicy(...))` |
| Summarize | `text = summarize_ticks(room.history[-20:], "room_name")` |
| Load configs | `configs = RoomConfig.load_directory("rooms/")` |
| Run agent | `await agent.run()` |
| Stop agent | `agent.stop()` |
