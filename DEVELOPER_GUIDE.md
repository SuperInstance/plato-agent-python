# Developer Guide — Plato Agent Python

## Architecture Overview

The Plato Agent Framework is an async Python library for connecting to Plato rooms (TCP servers running the Plato Engine Block), observing sensor data, and making decisions. It uses `asyncio` throughout — no threads, no blocking I/O.

### Module Map

| Module | Purpose |
|--------|---------|
| `client.py` | Async TCP client (`PlatoClient`) — connects to one room, sends commands, receives responses |
| `room.py` | State tracker (`RoomState`) — maintains sensor values, history, and alarms for one room |
| `agent.py` | Orchestrator (`PlatoAgent`) — connects multiple rooms, evaluates rules, handles escalations |
| `protocol.py` | Wire protocol parser/formatter — text-based, newline-delimited |
| `escalation.py` | Escalation policies (`EscalationPolicy`) — configurable rules for alerting humans |
| `config.py` | Room configuration loader (`RoomConfig`) — reads `.room.json` files |
| `summary.py` | Tick summarizer (`summarize_ticks`) — converts history to natural language |

### Data Flow

```
Plato Room (TCP) → PlatoClient → RoomState → PlatoAgent (rules + escalations)
                      ↑                                          ↓
                   commands ←─────────────────────────── actuate / escalate
```

### Client Internals (`client.py`)

`PlatoClient` manages a single TCP connection:

1. **Connect**: Opens a socket, performs handshake.
2. **Commands**: `tick()`, `history()`, `actuate()` — send a command, await the response.
3. **Subscribe**: `subscribe()` + `stream()` — the client enters streaming mode. `stream()` returns an `AsyncIterator` that yields `TickData` and alarm events as they arrive.
4. **Protocol**: All communication goes through `protocol.py`'s `format_command()` and `parse_response()`.

The client is intentionally simple — one room, one connection. For multi-room scenarios, use `PlatoAgent`.

### Room State (`room.py`)

`RoomState` maintains a rolling window of sensor data:

- **`sensor_values`**: Latest reading per sensor (dict).
- **`history`**: List of `Tick` objects, capped at `max_history`.
- **`alarms`**: Dict of alarm name → `AlarmState` (active/cleared, severity, message).

Key method: `get_trend(sensor, window)` computes mean, min, max, slope, and direction over the last N ticks. This is the primary input for rule conditions.

### Agent Loop (`agent.py`)

`PlatoAgent.run()` is the main event loop:

1. For each registered room, request a tick.
2. Update `RoomState` from the response.
3. Evaluate all rules against current room states.
4. Fire matching rule actions (with cooldown enforcement).
5. Check escalation policies for unhandled alarms.
6. Repeat.

**Rules** have three parts:
- `name` — Identifier for logging.
- `condition(room) → bool` — Synchronous predicate. Evaluates against `RoomState`.
- `action(room, agent) → coroutine` — Async handler. Has full access to the agent and its clients.
- `cooldown` — Seconds before the same rule can fire again for the same room.

**Cross-room correlation**: `get_cross_room_correlations()` compares sensor trends across rooms. Use it in rule actions to detect multi-room patterns.

### Escalation Policies (`escalation.py`)

`EscalationPolicy` determines when to involve a human:

- **`timeout`**: If an alarm stays active for N seconds without resolution, escalate.
- **`severity_threshold`**: Only escalate alarms at or above this severity.
- **`captain_present`**: If the responsible human is known to be absent, escalate immediately.
- **`max_escalations`**: Cap escalations per alarm (0 = unlimited).
- **`escalate_fn`**: Your async callback — send SMS, push notification, sound a buzzer, etc.

### Protocol (`protocol.py`)

Text-based, newline-delimited:

**Agent → Room:**
- `TICK` — Request current sensor reading.
- `HISTORY <n>` — Request last N ticks.
- `ACTUATE <name>=<value>` — Control an actuator.
- `SUBSCRIBE` / `UNSUBSCRIBE` — Toggle streaming.

**Room → Agent:**
- `TICK <ts> <json>` — Sensor data.
- `HISTORY <cursor> <count> <json>` — Historical data.
- `ALARM <name> <severity> <message>` — Alarm raised.
- `ALARM_CLEARED <name>` — Alarm resolved.
- `ACK <command>` — Command acknowledged.
- `ERROR <message>` — Error response.

### Extension Points

#### Custom Rule Actions

```python
async def my_action(room: RoomState, agent: PlatoAgent):
    client = agent.clients[room.name]
    # Your logic here
    await client.actuate("something", 42)

agent.add_rule("my_rule", lambda r: r.sensor_values["x"] > 10, my_action, cooldown=30)
```

#### Custom Escalation Handlers

```python
async def sms_alert(room_name: str, alarm: AlarmState):
    # Integrate with Twilio, SNS, etc.
    await send_sms(f"ALERT {room_name}: {alarm.message}")

agent.add_escalation(EscalationPolicy(
    timeout=60.0,
    severity_threshold="warning",
    escalate_fn=sms_alert,
))
```

#### LLM Integration

The `summarize_ticks()` function converts tick history to natural language. Feed this to any LLM:

```python
from plato_agent import summarize_ticks

summary = summarize_ticks(room.history[-20:], room_name="engine")
decision = await llm.chat(f"Room status:\n{summary}\nAction?")
```

### Testing Strategy

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests cover:
- Protocol parsing and formatting edge cases
- Room state updates, history rotation, trend computation
- Agent rule evaluation with cooldowns
- Escalation policy logic
- Config loading and validation

### Contributing

1. Use `async/await` throughout — no blocking calls in the agent loop.
2. Type hints on all public functions.
3. Add tests for new functionality.
4. Keep the client simple — one room, one connection. Complex orchestration belongs in `PlatoAgent`.
5. Run `python -m pytest tests/ -v` before submitting.
