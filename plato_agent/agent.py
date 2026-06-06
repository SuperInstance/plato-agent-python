"""PlatoAgent: manages multiple room connections, decision loop, and escalations."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .client import PlatoClient
from .escalation import EscalationPolicy
from .protocol import (
    AlarmCleared,
    AlarmNotification,
    TickData,
    parse_response,
)
from .room import AlarmState, RoomState

logger = logging.getLogger(__name__)

# Type aliases
ConditionFn = Callable[[RoomState], bool]
ActionFn = Callable[[RoomState, "PlatoAgent"], Awaitable[None]]


@dataclass
class Rule:
    """A decision rule: if condition is met, execute action."""
    name: str
    condition: ConditionFn
    action: ActionFn
    cooldown: float = 0.0
    _last_fired: float = field(default=0.0, repr=False)


class PlatoAgent:
    """Manages multiple room connections, evaluates rules, and handles escalations.

    Usage:
        agent = PlatoAgent()
        agent.add_room("engine", client)
        agent.add_rule("high_temp", lambda r: r.sensor_values.get("temp", 0) > 90, cool_down)
        await agent.run()

    Attributes:
        rooms: Room states keyed by name.
        clients: PlatoClient instances keyed by name.
        rules: Decision rules to evaluate.
        escalation_policies: Escalation policies to apply.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, RoomState] = {}
        self.clients: dict[str, PlatoClient] = {}
        self.rules: list[Rule] = []
        self.escalation_policies: list[EscalationPolicy] = []
        self._running: bool = False

    def add_room(self, name: str, client: PlatoClient) -> RoomState:
        """Register a room connection.

        Args:
            name: Room identifier.
            client: Connected PlatoClient instance.

        Returns:
            The RoomState for this room.
        """
        room = RoomState(name=name)
        self.rooms[name] = room
        self.clients[name] = client
        logger.info("Room registered: %s", name)
        return room

    def add_rule(
        self,
        name: str,
        condition: ConditionFn,
        action: ActionFn,
        cooldown: float = 0.0,
    ) -> None:
        """Add a decision rule.

        Args:
            name: Rule identifier.
            condition: Sync callable taking RoomState, returns True if rule should fire.
            action: Async callable taking (RoomState, PlatoAgent), executed when condition is True.
            cooldown: Minimum seconds between fires for this rule.
        """
        self.rules.append(Rule(name=name, condition=condition, action=action, cooldown=cooldown))
        logger.info("Rule added: %s", name)

    def add_escalation(self, policy: EscalationPolicy) -> None:
        """Add an escalation policy.

        Args:
            policy: EscalationPolicy instance.
        """
        self.escalation_policies.append(policy)
        logger.info("Escalation policy added (timeout=%.1fs)", policy.timeout)

    async def _process_tick(self, room_name: str, tick_data: TickData) -> None:
        """Process an incoming tick for a room."""
        room = self.rooms.get(room_name)
        if room is None:
            logger.warning("Tick for unknown room: %s", room_name)
            return
        room.update_from_tick(tick_data)

        # Evaluate rules
        for rule in self.rules:
            try:
                if rule.condition(room):
                    now = time.time()
                    if rule.cooldown > 0 and (now - rule._last_fired) < rule.cooldown:
                        continue
                    rule._last_fired = now
                    logger.info("Rule %s fired for room %s", rule.name, room_name)
                    await rule.action(room, self)
            except Exception:
                logger.exception("Error evaluating rule %s", rule.name)

    async def _process_alarm(self, room_name: str, alarm: AlarmNotification) -> None:
        """Process an alarm notification."""
        room = self.rooms.get(room_name)
        if room is None:
            logger.warning("Alarm for unknown room: %s", room_name)
            return
        room.raise_alarm(alarm.name, alarm.severity, alarm.message, timestamp=time.time())

        # Check escalation policies
        alarm_state = room.alarms[alarm.name]
        for policy in self.escalation_policies:
            # Force escalation for newly raised alarms that meet severity
            if policy.check(alarm_state, captain_present=False):
                # Bypass timeout check for new alarms by setting raised_at to past
                if alarm_state.raised_at > 0:
                    alarm_state.raised_at = time.time() - policy.timeout - 1
                if policy.check(alarm_state, captain_present=False):
                    await policy.escalate(room_name, alarm_state)

    async def _process_alarm_cleared(self, room_name: str, cleared: AlarmCleared) -> None:
        """Process an alarm cleared notification."""
        room = self.rooms.get(room_name)
        if room:
            room.clear_alarm(cleared.name, timestamp=time.time())

    async def run(self) -> None:
        """Main loop: receive ticks from all rooms, evaluate rules, handle escalations.

        Runs until stop() is called or all connections close.
        """
        self._running = True
        logger.info("Agent starting with %d rooms", len(self.rooms))

        tasks = []
        for name, client in self.clients.items():
            tasks.append(asyncio.create_task(
                self._room_loop(name, client), name=f"room-{name}"
            ))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            logger.info("Agent stopped")

    async def _room_loop(self, name: str, client: PlatoClient) -> None:
        """Event loop for a single room connection."""
        try:
            await client.subscribe()
            async for event in client.stream():
                if not self._running:
                    break
                if isinstance(event, TickData):
                    await self._process_tick(name, event)
                elif isinstance(event, AlarmNotification):
                    await self._process_alarm(name, event)
                elif isinstance(event, AlarmCleared):
                    await self._process_alarm_cleared(name, event)
        except ConnectionError:
            logger.error("Room %s connection lost", name)
        except Exception:
            logger.exception("Error in room %s loop", name)

    def stop(self) -> None:
        """Signal the agent to stop."""
        self._running = False

    def get_cross_room_correlations(self) -> list[dict[str, Any]]:
        """Find patterns and correlations across rooms.

        Looks for:
        - Same sensor trending in the same direction across rooms
        - Simultaneous alarms across rooms

        Returns:
            List of correlation findings.
        """
        correlations: list[dict[str, Any]] = []

        # Find common sensors across rooms
        all_sensors: dict[str, list[str]] = {}
        for room_name, room in self.rooms.items():
            for sensor in room.sensor_values:
                all_sensors.setdefault(sensor, []).append(room_name)

        # Check for same-direction trends
        for sensor, room_names in all_sensors.items():
            if len(room_names) < 2:
                continue
            directions: dict[str, str] = {}
            for room_name in room_names:
                trend = self.rooms[room_name].get_trend(sensor, window=10)
                directions[room_name] = trend.get("direction", "unknown")

            # All same direction?
            unique = set(directions.values())
            if len(unique) == 1 and "unknown" not in unique and "flat" not in unique:
                correlations.append({
                    "type": "shared_trend",
                    "sensor": sensor,
                    "direction": list(unique)[0],
                    "rooms": room_names,
                })

        # Simultaneous alarms
        rooms_with_alarms = [
            name for name, room in self.rooms.items()
            if room.active_alarms
        ]
        if len(rooms_with_alarms) >= 2:
            correlations.append({
                "type": "simultaneous_alarms",
                "rooms": rooms_with_alarms,
                "alarm_counts": {
                    name: len(self.rooms[name].active_alarms)
                    for name in rooms_with_alarms
                },
            })

        return correlations
