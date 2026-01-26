from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Mapping

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.logging import get_logger
from agentos.security.permissions import PermissionValidator
from agentos.tools.base import BaseTool

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
    ):
        self.agents = agents
        self.tools = tools
        self.permission_validator = permission_validator
        self.short_term = short_term
        self.working_state = working_state
        self.long_term = long_term
        self.agent_router = AgentRouter()
        self.tool_router = ToolRouter(top_k=3)
        self.logger = get_logger("agentos")

    def run(self, task: str, session_id: str, user_id: str, request_id: str | None = None) -> ExecutionResult:
        rid = request_id or str(uuid.uuid4())
        agent = self.agent_router.select_agent(task, self.agents)
        if agent is None:
            return ExecutionResult(agent_name="none", success=False, output="", error="No hay agentes cargados")

        selected_tools = self.tool_router.select_tools(task, agent.profile, self.tools, self.permission_validator)
        tool_map: Mapping[str, BaseTool] = {t.name: t for t in selected_tools}

        # Memoria (MVP)
        self.short_term.add(session_id, f"USER: {task}")
        retrieved = self.long_term.retrieve(task)

        ctx = AgentContext(
            request_id=rid,
            session_id=session_id,
            user_id=user_id,
            tools=tool_map,
            memory={"short_term": self.short_term.get(session_id), "retrieved": [it.text for it in retrieved]},
            logger=self.logger,
        )

        result = agent.execute(task, ctx)

        # Checkpoint
        self.working_state.save_checkpoint(
            session_id=session_id,
            name="last_result",
            data={"agent": result.agent_name, "success": result.success, "output": result.output, "error": result.error, "meta": result.meta},
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Guardar en memoria long-term (heurística)
        if result.success and result.output:
            self.long_term.add(result.output, tags=[agent.name])

        self.short_term.add(session_id, f"AGENT({agent.name}): {result.output}")
        return result
