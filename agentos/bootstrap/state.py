"""Centralized application state.

Inspired by jan-research src/bootstrap/state.ts:
all runtime singletons live in a single typed object, making it easy
to test (inject mock state), isolate sessions, and avoid scattered globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agentos.agents.base.agent_base import BaseAgent
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.metrics import MetricsCollector
from agentos.security.denial_tracking import DenialTracker
from agentos.security.permissions import PermissionValidator
from agentos.tasks.lifecycle import TaskState
from agentos.tools.base import BaseTool
from agentos.tools.executor import ToolExecutor


@dataclass
class AppState:
    """Single container for all runtime singletons.

    Every piece of mutable global state should live here instead of
    being scattered across module-level variables.
    """

    # Core components
    agents: List[BaseAgent] = field(default_factory=list)
    tools: List[BaseTool] = field(default_factory=list)
    permission_validator: Optional[PermissionValidator] = None
    orchestrator: Any = None  # SequentialOrchestrator | PlannerExecutorOrchestrator

    # Memory
    short_term: Optional[ShortTermMemory] = None
    working_state: Optional[WorkingStateStore] = None
    long_term: Optional[LongTermMemory] = None

    # Security
    denial_tracker: DenialTracker = field(default_factory=DenialTracker)

    # Observability
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    # Tool execution
    tool_executor: ToolExecutor = field(default_factory=ToolExecutor)

    # Task tracking
    task_states: Dict[str, TaskState] = field(default_factory=dict)

    # Metadata
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    orchestrator_type: str = "sequential"
    llm_provider: str = ""

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def healthz(self) -> Dict[str, Any]:
        """Return health check payload."""
        return {
            "ok": True,
            "agents": [a.name for a in self.agents],
            "tools": [t.name for t in self.tools],
            "uptime_seconds": round(self.uptime_seconds, 1),
            "orchestrator_type": self.orchestrator_type,
            "llm_provider": self.llm_provider or "none",
            "task_counts": self._task_counts(),
            "denial_stats": self.denial_tracker.all_stats(),
            "metrics": self.metrics.to_dict(),
        }

    def _task_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for ts in self.task_states.values():
            key = ts.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts
