"""Task lifecycle state machine with enforced transitions.

Inspired by jan-research src/tasks/types.ts pattern:
typed task states with predicates and guarded transitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


# Valid transitions: from -> set of allowed destinations
_TRANSITIONS: Dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.KILLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.KILLED: set(),
}


def is_terminal(status: TaskStatus) -> bool:
    return status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED}


class InvalidTransitionError(Exception):
    def __init__(self, current: TaskStatus, target: TaskStatus):
        super().__init__(f"Invalid transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


@dataclass
class TaskState:
    """Represents the full lifecycle state of a task."""

    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    task: str = ""
    session_id: str = ""
    user_id: str = ""
    status: TaskStatus = TaskStatus.PENDING

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    output: Optional[str] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def _transition(self, target: TaskStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidTransitionError(self.status, target)
        self.status = target

    def start(self) -> None:
        self._transition(TaskStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc)

    def complete(self, output: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._transition(TaskStatus.COMPLETED)
        self.completed_at = datetime.now(timezone.utc)
        self.output = output
        if meta:
            self.meta.update(meta)

    def fail(self, error: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._transition(TaskStatus.FAILED)
        self.completed_at = datetime.now(timezone.utc)
        self.error = error
        if meta:
            self.meta.update(meta)

    def kill(self) -> None:
        self._transition(TaskStatus.KILLED)
        self.completed_at = datetime.now(timezone.utc)

    @property
    def is_terminal(self) -> bool:
        return is_terminal(self.status)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task": self.task,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "meta": self.meta,
        }
