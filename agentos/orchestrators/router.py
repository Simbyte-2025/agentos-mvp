from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from agentos.security.permissions import PermissionValidator
from agentos.tools.base import BaseTool


class AgentRouter:
    def select_agent(self, task: str, agents: Sequence["BaseAgent"]):
        for a in agents:
            try:
                if a.can_handle(task):
                    return a
            except Exception:
                continue
        return agents[0] if agents else None


class ToolRouter:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def select_tools(
        self,
        task: str,
        agent_profile: str,
        tools: List[BaseTool],
        permission_validator: PermissionValidator,
    ) -> List[BaseTool]:
        allowed: List[BaseTool] = []
        for t in tools:
            decision = permission_validator.validate_tool_access(agent_profile, t.name, t.risk)
            if decision.allowed:
                allowed.append(t)

        scored = [(self._score(task, t), t) for t in allowed]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for score, t in scored[: self.top_k] if score > 0] or allowed[: self.top_k]

    @staticmethod
    def _score(task: str, tool: BaseTool) -> int:
        # Heurística MVP: overlap de palabras (sin embeddings)
        tokens = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", task.lower()))
        desc = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", (tool.description or "").lower()))
        return len(tokens.intersection(desc))
