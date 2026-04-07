from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Generator, List, Mapping, Optional

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from agentos.memory.compaction import ContextCompactor
from agentos.memory.long_term import LongTermMemory
from agentos.memory.session_transcript import SessionTranscript
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.logging import get_logger
from agentos.observability.metrics import MetricsCollector
from agentos.orchestrators.events import OrchestrationEvent, OrchestrationEventType
from agentos.security.denial_tracking import DenialTracker
from agentos.security.permissions import PermissionValidator
from agentos.tools.base import BaseTool
from agentos.tools.executor import ToolExecutor

from .router import AgentRouter, ToolRouter


class SequentialOrchestrator:
    def __init__(
        self,
        agents: List[BaseAgent],
        tools: List[BaseTool],
        permission_validator: PermissionValidator,
        short_term: ShortTermMemory,
        working_state: WorkingStateStore,
        long_term: LongTermMemory,
        metrics: Optional[MetricsCollector] = None,
        denial_tracker: Optional[DenialTracker] = None,
        tool_executor: Optional[ToolExecutor] = None,
    ):
        self.agents = agents
        self.tools = tools
        self.permission_validator = permission_validator
        self.short_term = short_term
        self.working_state = working_state
        self.long_term = long_term
        self.metrics = metrics or MetricsCollector()
        self.denial_tracker = denial_tracker or DenialTracker()
        self.tool_executor = tool_executor or ToolExecutor()
        self.agent_router = AgentRouter()
        self.tool_router = ToolRouter(top_k=3)
        self.compactor = ContextCompactor()
        self.logger = get_logger("agentos")

    def run(self, task: str, session_id: str, user_id: str, request_id: str | None = None) -> ExecutionResult:
        rid = request_id or str(uuid.uuid4())
        start = time.monotonic()
        self.metrics.record_request()

        # Session transcript persistence
        transcript = SessionTranscript(session_id)
        transcript.append("user", task)

        agent = self.agent_router.select_agent(task, self.agents)
        if agent is None:
            self.metrics.record_error("NO_AGENTS")
            return ExecutionResult(agent_name="none", success=False, output="", error="No hay agentes cargados")

        # Tool selection with denial tracking
        selected_tools = self._select_tools_with_tracking(task, agent.profile, session_id)
        tool_map: Mapping[str, BaseTool] = {t.name: t for t in selected_tools}

        # Memory
        self.short_term.add(session_id, f"USER: {task}")
        retrieved = self.long_term.retrieve(task)

        # Compaction check
        messages = self.short_term.get(session_id)
        if self.compactor.should_trim(messages):
            compacted = self.compactor.trim_tool_results(messages)
            # Replace short_term contents (rebuild)
            self.short_term._data[session_id].clear()
            for msg in compacted:
                self.short_term._data[session_id].append(msg)
            messages = compacted

        ctx = AgentContext(
            request_id=rid,
            session_id=session_id,
            user_id=user_id,
            tools=tool_map,
            memory={"short_term": messages, "retrieved": [it.text for it in retrieved]},
            logger=self.logger,
        )

        result = agent.execute(task, ctx)
        duration_ms = (time.monotonic() - start) * 1000

        # Checkpoint
        self.working_state.save_checkpoint(
            session_id=session_id,
            name="last_result",
            data={"agent": result.agent_name, "success": result.success, "output": result.output, "error": result.error, "meta": result.meta},
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Long-term memory
        if result.success and result.output:
            self.long_term.add(result.output, tags=[agent.name])

        self.short_term.add(session_id, f"AGENT({agent.name}): {result.output}")

        # Session transcript
        transcript.append("agent", result.output or "", meta={"agent": agent.name, "success": result.success})

        # Metrics
        if result.success:
            self.metrics.record_success(duration_ms=duration_ms)
        else:
            self.metrics.record_error(result.error or "UNKNOWN")

        return result

    def _select_tools_with_tracking(self, task: str, profile: str, session_id: str) -> List[BaseTool]:
        """Select tools with denial tracking integration."""
        allowed: List[BaseTool] = []
        for t in self.tools:
            decision = self.permission_validator.validate_tool_access(profile, t.name, t.risk)
            if decision.allowed:
                allowed.append(t)
                self.denial_tracker.record_success(session_id)
            else:
                self.denial_tracker.record_denial(session_id, t.name, t.risk)

        # Use ToolRouter scoring on allowed tools
        return self.tool_router.select_tools(task, profile, allowed, self.permission_validator)

    def run_stream(
        self, task: str, session_id: str, user_id: str, request_id: str | None = None
    ) -> Generator[OrchestrationEvent, None, None]:
        """Execute task yielding OrchestrationEvents for real-time streaming."""
        rid = request_id or str(uuid.uuid4())

        yield OrchestrationEvent(
            event_type=OrchestrationEventType.SUBTASK_STARTED,
            request_id=rid,
            data={"task": task, "agent": "selecting..."},
        )

        result = self.run(task, session_id, user_id, rid)

        if result.success:
            yield OrchestrationEvent(
                event_type=OrchestrationEventType.COMPLETED,
                request_id=rid,
                data={"agent": result.agent_name, "output": result.output},
            )
        else:
            yield OrchestrationEvent(
                event_type=OrchestrationEventType.ERROR,
                request_id=rid,
                data={"agent": result.agent_name, "error": result.error},
            )
