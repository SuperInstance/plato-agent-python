"""Tests for EscalationPolicy."""

import time
import pytest

from plato_agent.escalation import EscalationPolicy
from plato_agent.room import AlarmState


@pytest.fixture
def policy():
    return EscalationPolicy(timeout=1.0, severity_threshold="warning")


class TestEscalationCheck:
    def test_escalate_inactive_alarm(self, policy):
        alarm = AlarmState(name="test", severity="critical", message="!", active=False)
        assert not policy.check(alarm)

    def test_escalate_captain_present(self, policy):
        alarm = AlarmState(name="test", severity="critical", message="!", active=True, raised_at=0.0)
        assert not policy.check(alarm, captain_present=True)

    def test_below_severity_threshold(self, policy):
        alarm = AlarmState(name="test", severity="info", message="!", active=True, raised_at=0.0)
        assert not policy.check(alarm)

    def test_within_timeout(self, policy):
        alarm = AlarmState(
            name="test", severity="critical", message="!",
            active=True, raised_at=time.time(),
        )
        assert not policy.check(alarm)

    def test_past_timeout_escalates(self, policy):
        alarm = AlarmState(
            name="test", severity="critical", message="!",
            active=True, raised_at=time.time() - 10.0,
        )
        assert policy.check(alarm)

    def test_warning_meets_threshold(self, policy):
        alarm = AlarmState(
            name="test", severity="warning", message="!",
            active=True, raised_at=time.time() - 10.0,
        )
        assert policy.check(alarm)


class TestEscalationAction:
    @pytest.mark.asyncio
    async def test_escalate_calls_fn(self):
        called_with = {}

        async def my_fn(room, alarm):
            called_with["room"] = room
            called_with["alarm"] = alarm

        policy = EscalationPolicy(timeout=0.0, escalate_fn=my_fn)
        alarm = AlarmState(name="fire", severity="critical", message="Fire!", active=True)
        await policy.escalate("engine", alarm)
        assert called_with["room"] == "engine"
        assert called_with["alarm"] is alarm

    @pytest.mark.asyncio
    async def test_escalate_no_fn(self):
        """No escalation fn should not raise."""
        policy = EscalationPolicy(timeout=0.0)
        alarm = AlarmState(name="fire", severity="critical", message="Fire!", active=True)
        await policy.escalate("engine", alarm)  # Should not raise
