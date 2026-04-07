"""Structured event system for observability.

Inspired by jan-research src/services/analytics/:
typed event dataclasses that enable structured logging, metrics collection,
and programmatic event processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class BaseEvent:
    """Base for all structured events."""

    event_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = ""
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None and v != ""}


# --- Task events ---

@dataclass
class TaskStarted(BaseEvent):
    event_type: str = "task.started"
    task: str = ""
    user_id: str = ""


@dataclass
class TaskCompleted(BaseEvent):
    event_type: str = "task.completed"
    agent_name: str = ""
    duration_ms: Optional[float] = None
    output_length: int = 0


@dataclass
class TaskFailed(BaseEvent):
    event_type: str = "task.failed"
    agent_name: str = ""
    error: str = ""
    error_code: str = ""
    duration_ms: Optional[float] = None


# --- Subtask events ---

@dataclass
class SubtaskStarted(BaseEvent):
    event_type: str = "subtask.started"
    subtask_id: str = ""
    objetivo: str = ""


@dataclass
class SubtaskCompleted(BaseEvent):
    event_type: str = "subtask.completed"
    subtask_id: str = ""
    duration_ms: Optional[float] = None


@dataclass
class SubtaskFailed(BaseEvent):
    event_type: str = "subtask.failed"
    subtask_id: str = ""
    error: str = ""
    retry_count: int = 0


# --- Tool events ---

@dataclass
class ToolCalled(BaseEvent):
    event_type: str = "tool.called"
    tool_name: str = ""
    action: str = ""


@dataclass
class ToolCompleted(BaseEvent):
    event_type: str = "tool.completed"
    tool_name: str = ""
    duration_ms: Optional[float] = None
    success: bool = True


@dataclass
class ToolFailed(BaseEvent):
    event_type: str = "tool.failed"
    tool_name: str = ""
    error: str = ""
    duration_ms: Optional[float] = None


@dataclass
class ToolTimeout(BaseEvent):
    event_type: str = "tool.timeout"
    tool_name: str = ""
    timeout_seconds: int = 0


# --- LLM events ---

@dataclass
class LLMCalled(BaseEvent):
    event_type: str = "llm.called"
    provider: str = ""
    model: str = ""
    prompt_length: int = 0


@dataclass
class LLMCompleted(BaseEvent):
    event_type: str = "llm.completed"
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: Optional[float] = None


@dataclass
class LLMRetried(BaseEvent):
    event_type: str = "llm.retried"
    provider: str = ""
    attempt: int = 0
    delay_seconds: float = 0.0
    error: str = ""


@dataclass
class LLMFailed(BaseEvent):
    event_type: str = "llm.failed"
    provider: str = ""
    model: str = ""
    error: str = ""
    error_code: str = ""


# --- Permission events ---

@dataclass
class PermissionDenied(BaseEvent):
    event_type: str = "permission.denied"
    tool_name: str = ""
    action: str = ""
    profile: str = ""
    behavior: str = ""  # "deny" | "ask"


@dataclass
class PermissionEscalated(BaseEvent):
    event_type: str = "permission.escalated"
    consecutive_denials: int = 0
    total_denials: int = 0


# --- Compaction events ---

@dataclass
class CompactionTriggered(BaseEvent):
    event_type: str = "compaction.triggered"
    level: str = ""  # "trim" | "summarize"
    token_count: int = 0
    threshold: int = 0


@dataclass
class CompactionCompleted(BaseEvent):
    event_type: str = "compaction.completed"
    level: str = ""
    tokens_before: int = 0
    tokens_after: int = 0
