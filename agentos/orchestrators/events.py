"""Orchestration events for streaming execution.

Inspired by jan-research QueryEngine async generator pattern:
yield intermediate events as execution progresses, enabling
real-time progress tracking and SSE streaming.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class OrchestrationEventType(str, Enum):
    PLAN_CREATED = "plan_created"
    SUBTASK_STARTED = "subtask_started"
    SUBTASK_COMPLETED = "subtask_completed"
    SUBTASK_FAILED = "subtask_failed"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    REPLAN_TRIGGERED = "replan_triggered"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class OrchestrationEvent:
    """A single event emitted during orchestration."""

    event_type: OrchestrationEventType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""

    def to_sse(self) -> str:
        """Format as Server-Sent Event line."""
        import json
        payload = {"event": self.event_type.value, "ts": self.timestamp, **self.data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
