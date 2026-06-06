# Tutorial — Building a Smart Room Agent

This tutorial walks you through building a Python agent that monitors a room, reacts to alarms, and escalates to humans when needed.

**Prerequisites:** Python 3.9+, a running Plato Engine Block server.

## Step 1: Install and Connect

```bash
pip install plato-agent
```

Create `agent_tutorial.py`:

```python
import asyncio
from plato_agent import PlatoClient

async def main():
    # Connect to a Plato room
    client = PlatoClient()
    await client.connect("localhost", 7001)

    # Request a single tick
    tick = await client.tick()
    print(f"Sensors: {tick.sensors}")

    await client.disconnect()

asyncio.run(main())
```

Run it against a local engine block:

```bash
# Terminal 1: Start the server
cd /path/to/plato-engine-block-c && ./plato_server

# Terminal 2: Run your agent
python agent_tutorial.py
```

## Step 2: Subscribe to Live Updates

```python
import asyncio
from plato_agent import PlatoClient

async def main():
    client = PlatoClient()
    await client.connect("localhost", 7001)

    # Subscribe to streaming ticks
    await client.subscribe()

    count = 0
    async for event in client.stream():
        count += 1
        print(f"[{count}] {event.sensors}")
        if count >= 10:
            break

    await client.unsubscribe()
    await client.disconnect()

asyncio.run(main())
```

## Step 3: Build an Agent with Rules

Now let's add decision-making logic:

```python
import asyncio
from plato_agent import PlatoAgent, PlatoClient

async def main():
    agent = PlatoAgent()

    # Connect to the engine room
    client = PlatoClient()
    await client.connect("localhost", 7001)
    agent.add_room("engine", client)

    # Rule: overheat protection
    async def cool_down(room, agent):
        temp = room.sensor_values.get("cpu_temp", 0)
        print(f"🔥 Overheat detected! CPU at {temp}°C")

        # Activate cooling
        c = agent.clients[room.name]
        await c.actuate("fan_speed", 100)
        print("   → Fan speed set to 100%")

    agent.add_rule(
        name="overheat_protection",
        condition=lambda r: r.sensor_values.get("cpu_temp", 0) > 80,
        action=cool_down,
        cooldown=60.0,  # Don't re-trigger for 60 seconds
    )

    # Rule: low temperature warning
    async def warm_up(room, agent):
        temp = room.sensor_values.get("cpu_temp", 0)
        print(f"❄️  Low temp warning: CPU at {temp}°C")
        c = agent.clients[room.name]
        await c.actuate("fan_speed", 20)

    agent.add_rule(
        name="low_temp",
        condition=lambda r: r.sensor_values.get("cpu_temp", 0) < 50,
        action=warm_up,
        cooldown=120.0,
    )

    print("Agent running. Press Ctrl+C to stop.\n")
    try:
        await agent.run()
    except KeyboardInterrupt:
        agent.stop()

asyncio.run(main())
```

## Step 4: Add Escalation Policies

When the agent can't handle it alone, escalate:

```python
import asyncio
from plato_agent import PlatoAgent, PlatoClient, EscalationPolicy, AlarmState

async def send_sms(room_name: str, alarm: AlarmState):
    """Simulated SMS handler — replace with Twilio/SNS in production."""
    print(f"📱 SMS ALERT: [{alarm.severity}] {room_name} — {alarm.message}")

async def main():
    agent = PlatoAgent()

    client = PlatoClient()
    await client.connect("localhost", 7001)
    agent.add_room("engine", client)

    # Escalate critical alarms after 30 seconds
    agent.add_escalation(EscalationPolicy(
        timeout=30.0,
        severity_threshold="critical",
        max_escalations=3,
        escalate_fn=send_sms,
    ))

    # Escalate warnings after 5 minutes (lower urgency)
    agent.add_escalation(EscalationPolicy(
        timeout=300.0,
        severity_threshold="warning",
        max_escalations=1,
        escalate_fn=send_sms,
    ))

    try:
        await agent.run()
    except KeyboardInterrupt:
        agent.stop()

asyncio.run(main())
```

## Step 5: Multi-Room Monitoring

Connect to multiple rooms and correlate:

```python
async def main():
    agent = PlatoAgent()

    # Connect to multiple rooms
    for room_cfg in [("engine", 7001), ("bridge", 7002), ("hold", 7003)]:
        name, port = room_cfg
        client = PlatoClient()
        await client.connect("localhost", port)
        agent.add_room(name, client)

    # Cross-room rule: engine hot AND bilge rising = emergency
    async def emergency_protocol(room, agent):
        print("🚨 EMERGENCY: Engine overheating with rising bilge water!")
        # Shut down engine
        await agent.clients["engine"].actuate("shutdown", 1)
        # Alert everyone
        for name, client in agent.clients.items():
            await client.actuate("alarm_light", 1)

    agent.add_rule(
        "emergency",
        lambda r: (
            r.name == "engine" and
            r.sensor_values.get("cpu_temp", 0) > 90 and
            any(
                room.sensor_values.get("bilge_cm", 0) > 50
                for room in agent.rooms.values()
                if room.name == "bilge"
            )
        ),
        emergency_protocol,
        cooldown=0,  # No cooldown for emergencies
    )

    # Find cross-room correlations
    correlations = agent.get_cross_room_correlations()
    for c in correlations:
        print(f"Correlation: {c}")

    await agent.run()
```

## Step 6: LLM-Enhanced Agent

Use natural language for decision-making:

```python
from plato_agent import summarize_ticks

async def llm_rule(room, agent):
    summary = summarize_ticks(room.history[-20:], room.name)
    # Send to your LLM
    prompt = f"""Room status:\n{summary}\n
    Active alarms: {[a.name for a in room.active_alarms]}
    Decide: actuate, escalate, or ignore?"""
    
    # decision = await your_llm.chat(prompt)
    print(f"LLM prompt:\n{prompt}")

agent.add_rule("llm_supervisor", lambda r: bool(r.active_alarms), llm_rule)
```

## What You Built

- ✅ Async room client with streaming
- ✅ Rule-based decision engine with cooldowns
- ✅ Escalation policies for human alerts
- ✅ Multi-room correlation
- ✅ LLM integration pattern

## Next Steps

- Run `python examples/fishing_boat.py` to see a complete 4-room simulation
- Explore `examples/llm_agent.py` for a full LLM-powered agent
- Read the API reference in `README.md` for all available methods
