"""Tests for the wire protocol parser and formatter."""

import json
import pytest

from plato_agent.protocol import (
    AckResponse,
    AlarmCleared,
    AlarmNotification,
    ErrorResponse,
    HistoryData,
    ProtocolError,
    TickData,
    format_command,
    parse_response,
)


class TestParseTick:
    def test_valid_tick(self):
        payload = json.dumps({"temp": 72.5, "humidity": 45})
        result = parse_response(f"TICK 1700000000.0 {payload}")
        assert isinstance(result, TickData)
        assert result.timestamp == 1700000000.0
        assert result.sensors["temp"] == 72.5
        assert result.sensors["humidity"] == 45

    def test_tick_with_string_sensor(self):
        payload = json.dumps({"status": "ok", "count": 3})
        result = parse_response(f"TICK 100.0 {payload}")
        assert isinstance(result, TickData)
        assert result.sensors["status"] == "ok"
        assert result.sensors["count"] == 3

    def test_malformed_tick_missing_payload(self):
        with pytest.raises(ProtocolError):
            parse_response("TICK 100.0")

    def test_malformed_tick_bad_json(self):
        with pytest.raises(ProtocolError):
            parse_response("TICK 100.0 not-json")

    def test_empty_line(self):
        with pytest.raises(ProtocolError):
            parse_response("")

    def test_unknown_command(self):
        with pytest.raises(ProtocolError):
            parse_response("UNKNOWN stuff")


class TestParseHistory:
    def test_valid_history(self):
        ticks = [{"ts": 100.0, "sensors": {"a": 1}}, {"ts": 101.0, "sensors": {"a": 2}}]
        payload = json.dumps(ticks)
        result = parse_response(f"HISTORY 5 2 {payload}")
        assert isinstance(result, HistoryData)
        assert result.cursor == 5
        assert result.count == 2
        assert len(result.ticks) == 2
        assert result.ticks[0].timestamp == 100.0
        assert result.ticks[1].sensors["a"] == 2

    def test_empty_history(self):
        result = parse_response("HISTORY 0 0 []")
        assert isinstance(result, HistoryData)
        assert result.ticks == []


class TestParseAlarm:
    def test_alarm(self):
        result = parse_response("ALARM fire_alarm critical Temperature exceeds threshold")
        assert isinstance(result, AlarmNotification)
        assert result.name == "fire_alarm"
        assert result.severity == "critical"
        assert result.message == "Temperature exceeds threshold"

    def test_alarm_cleared(self):
        result = parse_response("ALARM_CLEARED fire_alarm")
        assert isinstance(result, AlarmCleared)
        assert result.name == "fire_alarm"


class TestParseMisc:
    def test_ack(self):
        result = parse_response("ACK ACTUATE pump=on")
        assert isinstance(result, AckResponse)
        assert result.command == "ACTUATE pump=on"

    def test_error(self):
        result = parse_response("ERROR Something went wrong")
        assert isinstance(result, ErrorResponse)
        assert result.message == "Something went wrong"


class TestFormatCommand:
    def test_tick(self):
        assert format_command("TICK") == "TICK"

    def test_history_default(self):
        assert format_command("HISTORY") == "HISTORY 10"

    def test_history_with_n(self):
        assert format_command("HISTORY", n=50) == "HISTORY 50"

    def test_actuate(self):
        assert format_command("ACTUATE", name="pump", value="on") == "ACTUATE pump=on"

    def test_actuate_missing_params(self):
        with pytest.raises(ProtocolError):
            format_command("ACTUATE", name="pump")

    def test_subscribe(self):
        assert format_command("SUBSCRIBE") == "SUBSCRIBE"

    def test_unsubscribe(self):
        assert format_command("UNSUBSCRIBE") == "UNSUBSCRIBE"

    def test_unknown_command(self):
        with pytest.raises(ProtocolError):
            format_command("BLAH")


class TestProtocolRoundtrip:
    def test_tick_roundtrip(self):
        """Format a command, parse the response."""
        cmd = format_command("TICK")
        assert cmd == "TICK"
        response = "TICK 100.0 {\"temp\": 50}"
        parsed = parse_response(response)
        assert isinstance(parsed, TickData)
        assert parsed.sensors["temp"] == 50
