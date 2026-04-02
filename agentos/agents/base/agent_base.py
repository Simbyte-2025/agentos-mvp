from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from agentos.tools.base import BaseTool


@dataclass
class ExecutionResult:
    agent_name: str
    success: bool
    output: str
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    request_id: str
    session_id: str
    user_id: str
    tools: Mapping[str, BaseTool]
    memory: Any
    logger: Any


class BaseAgent(ABC):
    max_turns: int = 10  # límite de turns por ejecución

    def __init__(self, name: str, description: str, profile: str):
        self.name = name
        self.description = description
        self.profile = profile

    @abstractmethod
    def can_handle(self, task: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        raise NotImplementedError
