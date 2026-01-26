from __future__ import annotations

from typing import Dict

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from .scaffold import scaffold_agent, scaffold_tool


class BuilderAgent(BaseAgent):
    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return "crear agente" in t or "crear tool" in t or "scaffold" in t

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        ctx.logger.info(
            "BuilderAgent executing",
            extra={"request_id": ctx.request_id, "session_id": ctx.session_id, "user_id": ctx.user_id, "agent": self.name},
        )
        return ExecutionResult(
            agent_name=self.name,
            success=True,
            output=(
                "BuilderAgent no interpreta lenguaje natural en MVP.\n"
                "Usa el endpoint /builder/scaffold con kind=agent|tool."
            ),
        )


def build_scaffold(kind: str, name: str, description: str, risk: str = "read") -> Dict:
    kind = (kind or "").strip().lower()
    if kind == "agent":
        return scaffold_agent(name=name, description=description)
    if kind == "tool":
        return scaffold_tool(name=name, description=description, risk=risk)
    raise ValueError("kind debe ser: agent | tool")
