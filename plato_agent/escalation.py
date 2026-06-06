"""Escalation policies for Plato agents."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .room import RoomState, AlarmState

logger = logging.getLogger(__name__)


@dataclass
class EscalationPolicy:
    """Determines when and how to escalate alarms to humans.

    Attributes:
        timeout: Seconds before an active alarm triggers escalation.
        severity_threshold: Minimum severity level to consider ('info', 'warning', 'critical').
        max_escalations: Maximum escalations per alarm (0 = unlimited).
        escalate_fn: Async callable invoked when escalation fires.
            Signature: async (room_name: str, alarm: AlarmState) -> None
    """

    timeout: float = 30.0
    severity_threshold: str = "warning"
    max_escalations: int = 0
    escalate_fn: Callable[[str, AlarmState], Awaitable[None]] | None = None

    _SEVERITY_ORDER: dict[str, int] = field(
        default_factory=lambda: {"info": 0, "warning": 1, "critical": 2, "emergency": 3},
        repr=False,
    )

    def _meets_severity(self, severity: str) -> bool:
        """Check if a severity meets the threshold."""
        alarm_level = self._SEVERITY_ORDER.get(severity, 0)
        threshold_level = self._SEVERITY_ORDER.get(self.severity_threshold, 0)
        return alarm_level >= threshold_level

    def check(self, alarm: AlarmState, captain_present: bool = False) -> bool:
        """Determine if an alarm should be escalated.

        Args:
            alarm: The alarm state to evaluate.
            captain_present: Whether a responsible human is currently present.

        Returns:
            True if the alarm should be escalated.
        """
        if not alarm.active:
            return False

        if captain_present:
            logger.debug(
                "Alarm %s not escalated: captain present", alarm.name
            )
            return False

        if not self._meets_severity(alarm.severity):
            logger.debug(
                "Alarm %s severity %s below threshold %s",
                alarm.name, alarm.severity, self.severity_threshold,
            )
            return False

        if alarm.raised_at > 0:
            elapsed = time.time() - alarm.raised_at
            if elapsed < self.timeout:
                logger.debug(
                    "Alarm %s not escalated yet: %.1fs < %.1fs timeout",
                    alarm.name, elapsed, self.timeout,
                )
                return False

        return True

    async def escalate(self, room_name: str, alarm: AlarmState) -> None:
        """Execute the escalation for an alarm.

        Args:
            room_name: Name of the room where the alarm originated.
            alarm: The alarm to escalate.
        """
        logger.warning(
            "ESCALATING alarm %s (severity=%s) in room %s: %s",
            alarm.name, alarm.severity, room_name, alarm.message,
        )
        if self.escalate_fn is not None:
            await self.escalate_fn(room_name, alarm)
        else:
            logger.info("No escalation function configured for alarm %s", alarm.name)
