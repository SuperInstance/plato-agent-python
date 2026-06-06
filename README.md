# Plato Agent Python

> Python agent framework for [Plato Engine Blocks](https://github.com/SuperInstance) — connect to rooms, observe ticks, send commands, and make decisions.

## What is the Plato Agent Framework?

Plato Engine Blocks are distributed IoT rooms — each one a self-contained unit with sensors, actuators, alarms, and a real-time tick system. The **Plato Agent Framework** is the Python library that lets any agent (LLM, script, or human operator) connect to these rooms, observe what's happening, send commands, and make intelligent decisions.

Think of it as the nervous system between your AI (or automation) and the physical world Plato rooms represent.

### Why this exists

- **Real-time observation**: Subscribe to room ticks and get streaming sensor data
- **Decision-making**: Define rules that evaluate room state and trigger actions
- **Escalation**: Configure policies that alert humans when things go wrong
- **Multi-room awareness**: Correlate events across rooms (is the engine overheating *and* the bilge rising?)
- **LLM-ready**: Feed summaries to language models for natural-language decision-making

## Quick Start

### Install

```bash
pip install plato-agent
```

For LLM integration:
```bash
pip install plato-agent[llm]
```

### Minimal Example

```python
import asyncio
from plato_agent import PlatoClient

async def main():
    client = PlatoClient()
    await client.connect("localhost", 7001)

    # Get current state
    tick = await client.tick()
    print(f"Temperature: {tick.sensors.get('temp')}")

    # Subscribe to real-time updates
    await client.subscribe()
    async for event in client.stream():
        print(f"Update: {event.sensors}")

    await client.disconnect()

asyncio.run(main())
```

### Agent with Rules

```python
import asyncio
from plato_agent import PlatoAgent, PlatoClient

async def main():
    agent = PlatoAgent()

    # Connect to the engine room
    client = PlatoClient()
    await client.connect("localhost", 7001)
    agent.add_room("engine", client)

    # Rule: if temperature exceeds 95°C, reduce RPM
    async def reduce_rpm(room, agent):
        print(f"Engine overheating! Temp: {room.sensor_values['temp']}")
        client = agent.clients[room.name]
        await client.actuate("rpm_limit", 1500)

    agent.add_rule(
        "overheat_protection",
        lambda r: r.sensor_values.get("temp", 0) > 95,
        reduce_rpm,
        cooldown=60.0,
    )

    # Run the agent
    await agent.run()

asyncio.run(main())
```

## Architecture

```
┌─────────────┐     TCP      ┌──────────────┐
│  Plato Room  │◄────────────►│  PlatoClient  │
│  (hardware)  │   protocol   │              │
└─────────────┘              └──────┬───────┘
                                    │
                                    ▼
                             ┌──────────────┐
                             │  RoomState    │
                             │  (tracks      │
                             │   sensors,    │
                             │   history,    │
                             │   alarms)     │
                             └──────┬───────┘
                                    │
                                    ▼
┌──────────┐   rules   ┌──────────────────────┐   escalations   ┌───────────────┐
│  Actions  │◄─────────│     PlatoAgent        │────────────────►│  Humans/Alerts │
│ (actuators│          │  (decision loop,       │                 │  (buzzer, SMS, │
│  commands)│          │   cross-room logic)    │                 │   push notifs) │
└──────────┘          └──────────────────────┘                  └───────────────┘
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| `PlatoClient` | `client.py` | Async TCP connection to a single room |
| `RoomState` | `room.py` | Tracks sensors, history, and alarms for one room |
| `PlatoAgent` | `agent.py` | Orchestrator: connects rooms, evaluates rules, handles escalations |
| `protocol.py` | `protocol.py` | Wire protocol parser and formatter |
| `EscalationPolicy` | `escalation.py` | Configurable rules for when to alert humans |
| `RoomConfig` | `config.py` | Load `.room.json` configuration files |
| `summarize_ticks` | `summary.py` | Convert tick history to natural language |

## API Reference

### PlatoClient

Async TCP client for connecting to a Plato room.

```python
client = PlatoClient()
```

#### Methods

| Method | Description |
|--------|-------------|
| `await connect(host, port)` | Establish TCP connection to a room |
| `await disconnect()` | Close the connection |
| `await tick() → TickData` | Request current sensor tick |
| `await history(n=10) → HistoryData` | Request last N ticks with cursor |
| `await actuate(name, value) → AckResponse` | Send actuator command |
| `await subscribe() → AckResponse` | Subscribe to real-time updates |
| `await unsubscribe() → AckResponse` | Stop receiving updates |
| `client.stream() → AsyncIterator` | Yield real-time ticks and alarms |

### RoomState

Tracks a room's sensor values, rolling history, and alarm states.

```python
room = RoomState(name="engine", max_history=1000)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Room identifier |
| `sensor_values` | `dict` | Latest sensor readings |
| `history` | `list[Tick]` | Rolling tick history |
| `alarms` | `dict[str, AlarmState]` | All alarms (active and cleared) |

#### Methods

| Method | Description |
|--------|-------------|
| `update_from_tick(tick) → Tick` | Process incoming tick, update state |
| `raise_alarm(name, severity, message) → AlarmState` | Raise a new alarm |
| `clear_alarm(name) → AlarmState \| None` | Clear an alarm |
| `active_alarms → list[AlarmState]` | Currently active alarms |
| `get_trend(sensor, window) → dict` | Compute trend statistics (mean, min, max, slope, direction) |

### PlatoAgent

Orchestrates multiple room connections with a decision loop.

```python
agent = PlatoAgent()
```

#### Methods

| Method | Description |
|--------|-------------|
| `add_room(name, client) → RoomState` | Register a room connection |
| `add_rule(name, condition, action, cooldown=0)` | Add a decision rule |
| `add_escalation(policy)` | Add an escalation policy |
| `await run()` | Start the main event loop |
| `stop()` | Signal the agent to stop |
| `get_cross_room_correlations() → list[dict]` | Find patterns across rooms |

### EscalationPolicy

Determines when and how to escalate alarms to humans.

```python
policy = EscalationPolicy(
    timeout=30.0,           # Seconds before escalating
    severity_threshold="warning",  # Minimum severity
    max_escalations=0,      # Max per alarm (0 = unlimited)
    escalate_fn=my_handler,  # async (room_name, alarm) -> None
)
```

#### Methods

| Method | Description |
|--------|-------------|
| `check(alarm, captain_present=False) → bool` | Should this alarm be escalated? |
| `await escalate(room_name, alarm)` | Execute the escalation |

### Wire Protocol

Text-based, newline-delimited protocol for room communication.

**Responses from room:**
- `TICK <timestamp> <json>` — Current sensor reading
- `HISTORY <cursor> <count> <json-array>` — Tick history
- `ALARM <name> <severity> <message>` — Alarm raised
- `ALARM_CLEARED <name>` — Alarm resolved
- `ACK <command>` — Command acknowledged
- `ERROR <message>` — Error response

**Commands from agent:**
- `TICK` — Request current tick
- `HISTORY <n>` — Request last N ticks
- `HISTORY_CURSOR <cursor>` — Navigate history
- `ACTUATE <name>=<value>` — Control an actuator
- `SUBSCRIBE` / `UNSUBSCRIBE` — Toggle real-time updates

### RoomConfig

Load room configuration from JSON files.

```python
config = RoomConfig.from_file("rooms/engine.room.json")
configs = RoomConfig.load_directory("rooms/")
```

### summarize_ticks

Convert tick history into human-readable text.

```python
from plato_agent import summarize_ticks
text = summarize_ticks(room.history[-20:], room_name="engine")
# "Room **engine**. 20 ticks over 19.0s. Sensors: temp: 89 (range 85–89, ↑)."
```

## The Fishing Boat Example

The `examples/fishing_boat.py` demonstrates a complete monitoring scenario with 4 rooms on a fishing vessel:

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Engine   │  │  Bridge   │  │   Hold    │  │  Galley   │
│          │  │          │  │          │  │          │
│ temp     │  │ heading  │  │ temp     │  │ smoke    │
│ rpm      │  │ speed    │  │ humidity │  │ temp     │
│ oil_pres │  │ wind     │  │ bilge    │  │ propane  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
      │              │              │              │
      └──────────────┴──────────────┴──────────────┘
                          │
                   ┌──────────────┐
                   │  PlatoAgent   │
                   │              │
                   │ Rules:       │
                   │ • overheat   │
                   │ • high_bilge │
                   │              │
                   │ Escalations: │
                   │ • buzzer     │
                   │ • SMS        │
                   └──────────────┘
```

Run it:
```bash
python examples/fishing_boat.py
```

The demo simulates normal operation, then triggers an engine overheat alarm and rising bilge water, demonstrating rules firing and escalation policies in action.

## How to Write a Custom Agent

### 1. Define your rooms

```python
agent = PlatoAgent()

for room_config in RoomConfig.load_directory("rooms/"):
    client = PlatoClient()
    await client.connect(room_config.host, room_config.port)
    agent.add_room(room_config.name, client)
```

### 2. Add decision rules

Rules have a synchronous condition function and an async action:

```python
# Condition: returns True when rule should fire
# Action: async function with access to room state and agent

agent.add_rule(
    name="low_oil_pressure",
    condition=lambda room: room.sensor_values.get("oil_pressure", 100) < 20,
    action=async def(room, agent):
        await agent.clients[room.name].actuate("engine", "shutdown")
        await agent.clients[room.name].actuate("alarm_light", "on")
    ,
    cooldown=30.0,  # Don't re-trigger for 30 seconds
)
```

### 3. Configure escalations

```python
async def send_sms(room_name, alarm):
    # Your SMS logic here
    print(f"SMS: {room_name} - {alarm.message}")

agent.add_escalation(EscalationPolicy(
    timeout=60.0,
    severity_threshold="critical",
    escalate_fn=send_sms,
))
```

### 4. Run

```python
await agent.run()  # Blocks until stop() is called
```

## LLM Integration Patterns

### Pattern 1: Summarize and Decide

The simplest pattern — summarize room state and ask an LLM what to do:

```python
from plato_agent import summarize_ticks, PlatoAgent

summary = summarize_ticks(room.history[-20:], room.name)

# Send to your LLM
decision = await llm.chat(
    f"Room status:\n{summary}\n\nWhat should we do?"
)
```

### Pattern 2: LLM as a Rule Action

Use an LLM to decide actions when rules fire:

```python
async def llm_action(room, agent):
    summary = summarize_ticks(room.history[-10:], room.name)
    decision = await llm.chat(
        f"Alarm triggered in {room.name}:\n{summary}\n"
        f"Active alarms: {[a.name for a in room.active_alarms]}\n"
        f"Decide: actuate, escalate, or ignore?"
    )
    # Parse and execute the decision
    await execute_decision(decision, room, agent)

agent.add_rule("llm_supervisor", lambda r: bool(r.active_alarms), llm_action)
```

### Pattern 3: Full Agent with LLM

See `examples/llm_agent.py` for a complete example using OpenAI's API.

```bash
OPENAI_API_KEY=sk-... python examples/llm_agent.py
```

## Connection to the SuperInstance Ecosystem

Plato Agent Python is part of the [SuperInstance](https://github.com/SuperInstance) ecosystem:

- **Plato Engine Blocks** — The hardware/firmware: room servers that expose sensors, actuators, and alarms over TCP
- **plato-agent-python** — This library: the Python interface for agents to connect, observe, and control rooms
- **SuperInstance** — The broader platform: bringing AI agents into the real world through IoT

### The Flow

```
Physical World → Sensors → Plato Room (TCP Server) → plato-agent-python → Your Agent / LLM
                                    ↑                                              |
                                    └──── Actuator Commands ←────────────────────────┘
```

Agents don't talk to hardware directly. They talk to Plato rooms, which mediate between the digital and physical worlds safely. This means:

1. **Safety**: The room validates all actuator commands
2. **Decoupling**: Swap sensors without changing agent code
3. **Observability**: Every tick is logged, every alarm tracked
4. **Multi-agent**: Multiple agents can observe the same room simultaneously

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_protocol.py -v
```

## License

MIT — see [LICENSE](LICENSE).
