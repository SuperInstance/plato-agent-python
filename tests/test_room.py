"""Tests for RoomState."""

import pytest

from plato_agent.protocol import TickData
from plato_agent.room import AlarmState, RoomState, Tick


class TestRoomStateUpdate:
    def test_update_from_tick(self):
        room = RoomState(name="engine")
        tick = TickData(timestamp=100.0, sensors={"temp": 72.5, "pressure": 14.7})
        processed = room.update_from_tick(tick)
        assert isinstance(processed, Tick)
        assert processed.room_name == "engine"
        assert room.sensor_values["temp"] == 72.5
        assert room.sensor_values["pressure"] == 14.7

    def test_multiple_updates(self):
        room = RoomState(name="bridge")
        for i in range(5):
            room.update_from_tick(TickData(timestamp=100.0 + i, sensors={"temp": 70 + i}))
        assert len(room.history) == 5
        assert room.sensor_values["temp"] == 74

    def test_history_rolling_window(self):
        room = RoomState(name="hold", max_history=3)
        for i in range(10):
            room.update_from_tick(TickData(timestamp=float(i), sensors={"v": i}))
        assert len(room.history) == 3
        assert room.history[0].sensors["v"] == 7
        assert room.history[-1].sensors["v"] == 9


class TestRoomStateTrend:
    def test_rising_trend(self):
        room = RoomState(name="engine")
        for i in range(10):
            room.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 70 + i}))
        trend = room.get_trend("temp")
        assert trend["direction"] == "rising"
        assert trend["min"] == 70
        assert trend["max"] == 79
        assert trend["slope"] > 0

    def test_falling_trend(self):
        room = RoomState(name="engine")
        for i in range(10):
            room.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 80 - i}))
        trend = room.get_trend("temp")
        assert trend["direction"] == "falling"

    def test_flat_trend(self):
        room = RoomState(name="engine")
        for i in range(5):
            room.update_from_tick(TickData(timestamp=float(i), sensors={"temp": 72}))
        trend = room.get_trend("temp")
        assert trend["direction"] == "flat"

    def test_trend_with_window(self):
        room = RoomState(name="engine")
        for i in range(20):
            room.update_from_tick(TickData(timestamp=float(i), sensors={"v": i}))
        trend = room.get_trend("v", window=5)
        assert trend["count"] == 5
        assert trend["min"] == 15
        assert trend["max"] == 19

    def test_trend_missing_sensor(self):
        room = RoomState(name="engine")
        room.update_from_tick(TickData(timestamp=1.0, sensors={"temp": 72}))
        trend = room.get_trend("nonexistent")
        assert trend == {}

    def test_trend_empty_history(self):
        room = RoomState(name="empty")
        trend = room.get_trend("temp")
        assert trend == {}


class TestRoomStateAlarms:
    def test_raise_alarm(self):
        room = RoomState(name="engine")
        alarm = room.raise_alarm("overheat", "critical", "Engine overheating", timestamp=100.0)
        assert alarm.active
        assert alarm.severity == "critical"
        assert "overheat" in room.alarms

    def test_clear_alarm(self):
        room = RoomState(name="engine")
        room.raise_alarm("overheat", "critical", "Too hot", timestamp=100.0)
        cleared = room.clear_alarm("overheat", timestamp=200.0)
        assert cleared is not None
        assert not cleared.active
        assert cleared.cleared_at == 200.0

    def test_clear_nonexistent_alarm(self):
        room = RoomState(name="engine")
        assert room.clear_alarm("nope") is None

    def test_active_alarms_property(self):
        room = RoomState(name="engine")
        room.raise_alarm("a1", "warning", "first")
        room.raise_alarm("a2", "critical", "second")
        room.clear_alarm("a1")
        assert len(room.active_alarms) == 1
        assert room.active_alarms[0].name == "a2"
