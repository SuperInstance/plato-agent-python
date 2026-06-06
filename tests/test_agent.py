"""Tests for PlatoAgent."""

import asyncio
import json
import time
import pytest

from plato_agent.agent import PlatoAgent
from plato_agent.client import PlatoClient
from plato_agent.escalation import EscalationPolicy
from plato_agent.protocol import TickData
from plato_agent.room import AlarmState


class TestAgentRules:
    @pytest.mark.asyncio
    async def test_rule_fires(self):
        agent = PlatoAgent()
        room = agent.rooms["test"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="test")

        fired = []

        async def my_action(room, agent):
            fired.append(room.name)

        agent.add_rule(
            "high_temp",
            lambda r: r.sensor_values.get("temp", 0) > 90,
            my_action,
        )

        await agent._process_tick("test", TickData(timestamp=1.0, sensors={"temp": 95}))
        assert fired == ["test"]

    @pytest.mark.asyncio
    async def test_rule_does_not_fire(self):
        agent = PlatoAgent()
        room = agent.rooms["test"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="test")

        fired = []

        async def my_action(room, agent):
            fired.append(True)

        agent.add_rule("high_temp", lambda r: r.sensor_values.get("temp", 0) > 90, my_action)
        await agent._process_tick("test", TickData(timestamp=1.0, sensors={"temp": 80}))
        assert not fired

    @pytest.mark.asyncio
    async def test_rule_cooldown(self):
        agent = PlatoAgent()
        room = agent.rooms["test"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="test")

        fired = []

        async def my_action(room, agent):
            fired.append(True)

        agent.add_rule("hot", lambda r: r.sensor_values.get("temp", 0) > 90, my_action, cooldown=10.0)

        await agent._process_tick("test", TickData(timestamp=1.0, sensors={"temp": 95}))
        assert len(fired) == 1

        # Second fire should be within cooldown
        await agent._process_tick("test", TickData(timestamp=2.0, sensors={"temp": 96}))
        assert len(fired) == 1  # Still 1 due to cooldown


class TestAgentCrossRoom:
    def test_cross_room_rising_correlation(self):
        agent = PlatoAgent()
        r1 = agent.rooms["engine"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="engine")
        r2 = agent.rooms["hold"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="hold")

        for i in range(10):
            r1.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 70 + i}))
            r2.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 60 + i}))

        corrs = agent.get_cross_room_correlations()
        trend_corrs = [c for c in corrs if c["type"] == "shared_trend"]
        assert len(trend_corrs) >= 1
        assert trend_corrs[0]["direction"] == "rising"
        assert set(trend_corrs[0]["rooms"]) == {"engine", "hold"}

    def test_no_correlation_single_room(self):
        agent = PlatoAgent()
        r1 = agent.rooms["engine"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="engine")
        for i in range(10):
            r1.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 70 + i}))
        corrs = agent.get_cross_room_correlations()
        shared = [c for c in corrs if c["type"] == "shared_trend"]
        assert len(shared) == 0

    def test_simultaneous_alarms(self):
        agent = PlatoAgent()
        r1 = agent.rooms["engine"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="engine")
        r2 = agent.rooms["hold"] = __import__("plato_agent.room", fromlist=["RoomState"]).RoomState(name="hold")
        r1.raise_alarm("fire", "critical", "Engine fire")
        r2.raise_alarm("flood", "warning", "Bilge water rising")
        corrs = agent.get_cross_room_correlations()
        alarm_corrs = [c for c in corrs if c["type"] == "simultaneous_alarms"]
        assert len(alarm_corrs) == 1
        assert set(alarm_corrs[0]["rooms"]) == {"engine", "hold"}
